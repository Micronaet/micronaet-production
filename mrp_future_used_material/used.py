# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class MrpProductionFutureMode(orm.Model):
    """ Model name: MrpProductionFutureMode
    """
    
    _name = 'mrp.production.future.move'
    _description = 'MRP temp future move'
    _rec_name = 'product_id'
    
    _columns = { 
        'mrp_id': fields.many2one(
            'mrp.production', 'Production'),
        'sol_id': fields.many2one(
            'sale.order.line', 'Order line'),
        'date': fields.date('Date', required=True),
        'week': fields.integer('Week #'),
        'product_id': fields.many2one(
            'product.product', 'Product', required=True),
        'remain': fields.float('Remain', digits=(16, 3), required=True),
        'material_id': fields.many2one(
            'product.product', 'Material', required=True),
        'qty': fields.float('Q.', digits=(16, 3), required=True),
        }

class ProductProduct(orm.Model):
    """ Model name: Product product
    """
    
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def open_button_form(self, cr, uid, ids, context=None):
        ''' Open form button
        '''
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': [(False, 'form'),(False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
    
    _columns = {
        'mx_mrp_future_qty': fields.float(
            'Q. MRP future', digits=(16, 3)),
        }    

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    
    _inherit = 'mrp.production'

    # Scheduled action:
    def regenerate_production_future_movement(self, cr, uid, 
            department_select=None, only_hw=False, send_mail=True, 
            regenerate=True, context=None):
        ''' Regenerate future movement database 
        '''
        _logger.info('Start update future movement of MRP')
        
        # Pool used:
        move_pool = self.pool.get('mrp.production.future.move')
        sol_pool = self.pool.get('sale.order.line')
        product_pool = self.pool.get('product.product')
        cron_pool = self.pool.get('ir.cron')

        if department_select is None:
            department_select = []
        else:
            if type(department_select) not in (list, tuple):
                department_select = department_select.split(',')
                
        _logger.info('''
            Parameter: 
            [Department %s] [Only HW: %s] [mail: %s] [Regenerate %s]
            ''' % (
                department_select,
                only_hw,
                send_mail,
                regenerate,
                ))

        if regenerate:
            # -----------------------------------------------------------------
            # Reset situations:
            # -----------------------------------------------------------------
            _logger.info('Remove all movements')
            # Remove all movement
            move_ids = move_pool.search(cr, uid, [], context=context)
            move_pool.unlink(cr, uid, move_ids, context=context)
            _logger.info('Deletet future movement')
            
            # Reset total in product:
            cr.execute('UPDATE product_product set mx_mrp_future_qty=0;')
            _logger.info('Reset product total')
        
            # -----------------------------------------------------------------
            # Load all line with remain:
            # -----------------------------------------------------------------
            _logger.info('Explore MRP situation for future movements')
            sol_ids = sol_pool.search(cr, uid, [
                ('mrp_id.state', 'not in', ('cancel', 'done')), # XXX draft?            
                ], context=context)

            dbs = {} # for speed product bom load
            total = {}
            i_tot = len(sol_ids)
            i = 0
            for sol in sol_pool.browse(cr, uid, sol_ids, context=context):
                i += 1
                _logger.info('SOL analysed: %s of %s' % (i, i_tot))
                
                # Qty used:
                oc_qty = sol.product_uom_qty
                delivered_qty = sol.delivered_qty
                b_qty = sol.product_uom_maked_sync_qty
                
                if delivered_qty > b_qty: # Delivered
                    remain = oc_qty - delivered_qty
                else: # Produced:
                    remain = oc_qty - b_qty
                if not remain: 
                    continue # jump product done or delivered
                    
                product = sol.product_id
                mrp = sol.mrp_id
                data = {
                    # MRP data:
                    'mrp_id': mrp.id,
                    'date': mrp.date_planned,                    
                    # SOL data:
                    'sol_id': sol.id,
                    'product_id': product.id,
                    'remain': remain,                
                    }
                if product not in dbs:
                    dbs[product] = product.dynamic_bom_line_ids

                for line in dbs[product]:
                    if department_select and line.category_id and \
                            line.category_id.department not in \
                            department_select:
                        continue # jump department not used

                    material = line.product_id                
                    if material.bom_placeholder or material.bom_alternative:
                        continue # jump placeholder

                    qty = remain * line.product_qty
                    if material.id in total:
                        total[material.id] += qty
                    else:   
                        total[material.id] = qty

                    data.update({
                        'material_id': material.id,
                        'qty': qty,
                        })
                    move_pool.create(cr, uid, data, context=context)    

            # -----------------------------------------------------------------
            # Load all total in product:
            # -----------------------------------------------------------------
            _logger.info('Create future movement')
            for product_id, mx_mrp_future_qty in total.iteritems():
                product_pool.write(cr, uid, product_id, {
                    'mx_mrp_future_qty': mx_mrp_future_qty,
                    }, context=context)
            _logger.info('End update future movement of MRP')

        # ---------------------------------------------------------------------
        # Send email with available data
        # ---------------------------------------------------------------------
        _logger.info('Create mail for send report')
        datas = {
            'model': 'mrp.production.future.move',
            #'active_id': False,
            #'active_ids': [],
            #'context': context,
            }

        # ---------------------------------------------------------------------
        # Call report:            
        # ---------------------------------------------------------------------
        try:
            result, extension = openerp.report.render_report(
                cr, uid, [], #future_ids, 
                'mrp_available_future_hw_report_status', 
                datas, context)
        except:
            _logger.error('Error generation TX report [%s]' % (
                sys.exc_info(),))
            return False    

        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')
        attachments = [('Semilavorati_disponibili_%s.odt' % now, result)]
                
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        if not send_mail:
            return True
            
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 
            'mrp_future_used_material', 'group_mrp_hw_available_status')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', body='''
                Situazione semilavorati disponibili in base alle produzioni
                schedulate future.
                ''', 
            subject=u'Invio automatico stato disponibilità materiali: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments, 
            context=context,
            )
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
