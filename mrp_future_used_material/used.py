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
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # Fields function:    
    def _get_mx_mrp_future_qty(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate future total for product
        '''    
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = 0.0
            for future in product.future_ids:
                res[product.id] += future.qty
        return res
        
    _columns = {
        'mx_mrp_future_qty': fields.function(
            _get_mx_mrp_future_qty, method=True, 
            type='float', string='Q. MRP future', store=False),                         
        'future_ids': fields.one2many(
            'mrp.production.future.move', 'material_id', 'Future material'),
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
        log_pool = self.pool.get('ir.activity.log.event')
        move_pool = self.pool.get('mrp.production.future.move')
        sol_pool = self.pool.get('sale.order.line')
        product_pool = self.pool.get('product.product')
        cron_pool = self.pool.get('ir.cron')

        # Log event:
        event_id = log_pool.log_start_event(
            cr, uid, 'FUTUREMRP', context=context)
        event_data = {}

        if type(department_select) not in (list, tuple): # End with error!
            log_pool.log_data(u'No department list passed: %s' % (
                department_select,
                ), event_data, mode='error')
            return log_pool.log_stop_event(
                cr, uid, event_id, event_data, context=context)                    
        
        log_pool.log_data(u'''Parameter: 
            [Department %s] [Only HW: %s] [mail: %s] [Regenerate %s]''' % (
                department_select,
                only_hw,
                send_mail,
                regenerate,
                ), event_data)

        if regenerate:
            # -----------------------------------------------------------------
            # Reset situations:
            # -----------------------------------------------------------------
            log_pool.log_data(u'Remove all movements', event_data)
            
            # Remove all movement
            move_ids = move_pool.search(cr, uid, [], context=context)
            move_pool.unlink(cr, uid, move_ids, context=context)
            log_pool.log_data(u'Deleted future movement', event_data)
            
            # -----------------------------------------------------------------
            # Load all line with remain:
            # -----------------------------------------------------------------
            log_pool.log_data(
                u'Explore MRP situation for future movements', 
                event_data,
                )
            sol_ids = sol_pool.search(cr, uid, [
                ('mrp_id.state', 'not in', ('cancel', 'done')), # XXX draft?            
                ], context=context)

            dbs = {} # for speed product bom load
            #    key = product browse, 
            #    value = list of (material, quantity) cut category and no p.h.
            i_tot = len(sol_ids)
            i = 0
            log_pool.log_data(u'SOL total: %s' % len(sol_ids), event_data)
            for sol in sol_pool.browse(cr, uid, sol_ids, context=context):
                i += 1
                _logger.info(u'SOL analysed: %s of %s' % (i, i_tot))
                
                # XXX Qty used (clean assigned that will not be produced):
                oc_qty = sol.product_uom_qty - sol.mx_assigned_qty
                
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
                
                # Speed up loading now elements:    
                if product not in dbs:
                    dbs[product] = [] # list of elements (component, qty)
                    for line in product.dynamic_bom_line_ids:
                        if not (line.category_id and \
                                line.category_id.department in
                                    department_select):
                            continue # jump department not used
                        cmpt = line.product_id                
                        if cmpt.bom_placeholder or cmpt.bom_alternative:
                            continue # jump placeholder
                        dbs[product].append((cmpt, line.product_qty))                        

                for (cmpt, product_qty) in dbs[product]:
                    data.update({
                        'material_id': cmpt.id,
                        'qty': remain * product_qty,
                        })
                    move_pool.create(cr, uid, data, context=context)    

        # ---------------------------------------------------------------------
        # Send email with available data
        # ---------------------------------------------------------------------
        log_pool.log_data(u'Create mail for send report', event_data)
        datas = {
            'model': 'mrp.production.future.move',
            #'active_id': False, 'active_ids': [], 'context': context,
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
            log_pool.log_data(u'Error generation TX report [%s]' % (
                sys.exc_info(), ), event_data, mode='error')
            log_pool.log_stop_event(
                cr, uid, event_id, event_data, context=context)    
            return False    

        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')
        attachments = [('Semilavorati_disponibili_%s.odt' % now, result)]
                
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        if not send_mail:
            # Log stop event:    
            log_pool.log_data(u'No mail report sent', event_data)
            log_pool.log_stop_event(
                cr, uid, event_id, event_data, context=context)    
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
            
        # Log stop event:
        log_pool.log_data(u'Mail report sent: partner_ids: %s' % (
            partner_ids, ), event_data)
        log_pool.log_stop_event(
            cr, uid, event_id, event_data, context=context)    
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
