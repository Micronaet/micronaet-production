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
from openerp import netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class res_company(orm.Model):
    ''' Add fields for report in workcenter
    '''
    _name = 'res.company'
    _inherit = 'res.company'
    
    _columns = {
        'max_hour_man': fields.integer('Max hour/man a day', 
            help='Max time * employee for a work day'),
        # TODO not used yet
        'max_employee': fields.integer('Ordinary hour', 
            help='Max number of employee'),
        }

class mrp_workcenter(orm.Model):
    ''' Add fields for report in workcenter
    '''
    _name = 'mrp.workcenter'
    _inherit = 'mrp.workcenter'
    
    _columns = {
        'ordinary_hour': fields.integer('Ordinary hour', 
            help='Normal work hours'),
        'extra_hour': fields.integer('Ordinary hour', 
            help='Extra work max hours'),
        }

class mrp_bom_lavoration(orm.Model):
    ''' Add relation fields (use same element in BOM and in production)
    '''
    _name = 'mrp.bom.lavoration'
    _inherit = 'mrp.bom.lavoration'

    # -------
    # Button:    
    # -------
    def open_lavoration_wc(self, cr, uid, ids, context=None):
        ''' Open in calendar all lavorations for this workcenter
        '''
        return self.pool.get('mrp.production').open_view(
            cr, uid, ids, 'workcenter', context=context) or {}

    _columns = {
        'production_id': fields.many2one('mrp.production', 'Production', 
            ondelete='cascade'),            
        'total_duration': fields.float('Duration', digits=(10, 2),
            help="Duration in hour:minute for lavoration of quantity piece"),

        # TODO move in another module after DEMO    
        'real_duration': fields.float('Duration', digits=(10, 2),
            help="Real duration in hour:minute for lavoration of quantity piece"),
        'scheduled_ids': fields.one2many('mrp.production.workcenter.line',
            'lavoration_id', 'Scheduled lavorations'),    

        }

class bom_production(orm.Model):
    ''' Lavoration for BOM extra fields for manage production
        Add totals and link to production order for use same element also 
        for exploded BOM in productions
    '''

    _inherit = 'mrp.production'

    # --------
    # Utility:
    # --------
    def open_view(self, cr, uid, ids, open_mode, context=None):
        ''' Open in calendar all lavorations for this production:
            open_mode: 'production', 'workcenter' for setup filters
        '''
        # Find record or filter to show:
        if open_mode == 'workcenter':
            lavoration_proxy = self.pool.get(
                'mrp.bom.lavoration').browse(
                    cr, uid, ids, context=context)[0]            
            production_id = lavoration_proxy.production_id.id
            workcenter_id = lavoration_proxy.line_id.id
        else:
            production_id = ids[0]
            workcenter_id = False

        # Return view:
        name = _('Production elements')
        view_type = 'form'
        view_mode = 'tree,form,calendar'
        model = 'mrp.production.workcenter.line'
        domain = []
        module = 'mrp'
        args = []
        res_id = False
        view_context = {'search_default_production_id': production_id}
        if workcenter_id:
            view_context['search_default_workcenter_id'] = workcenter_id

        # Read all parameters for view:
        default = False # TODO default view name
        view_id = False
        views = []

        data_pool = self.pool.get('ir.model.data')
        for view in ['form', 'tree', 'calendar', 'gantt', 'graph']:
            try: # compose views parameter:
                if view in args:
                    name, item_id = data_pool.get_object_reference(
                        cr, uid, module, args.get(view))
                    views.append((item_id, view)) # es. [(form_id, 'form')],
                    if default == view: #Note:  Use as first view
                        view_id = item_id
            except:
                pass

        return {
            'name': name,
            'view_type': view_type,
            'view_mode': view_mode,
            'res_model': model,
            'res_id': res_id,
            'view_id': view_id,
            'views': views,
            'domain': domain,
            'context': view_context,
            'type': 'ir.actions.act_window',
            }

    # -------    
    # Button:
    # -------    
    def schedule_schedule(self, cr, uid, ids, context=None):
        ''' Schedule activities
        '''
        if context is None: 
            context = {}

        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Load information for lavoration:
        workcenter_pool = self.pool.get('mrp.production.workcenter.line')

        # Parameters:            
        max_day = 5 # < saturday
        hour_a_day = 8.0 # work hour per day   # TODO parametrize
        start_hour = 7.0 # # GMT               # TODO parametrize
            
        # TODO set for days elements (TODO what about leave days?)
        schedule_type = mrp_proxy.workhour_id
        # TODO Change:
        hour_a_day = 10.0
        max_day = 6
        
        current_date = datetime.strptime(
            mrp_proxy.schedule_from_date, DEFAULT_SERVER_DATE_FORMAT)

        sequence = 0
        remain_hour_a_day = 0.0
        i = 0
        current_date_text = False
        for lavoration in self.lavoration_ids:
            i += 1
            total_hour = lavoration.duration
            
            while total_hour > 0.0:  
                if current_date.weekday() >= max_day: # sat, sun:
                    current_date = current_date + timedelta(days=1)
                    continue
                sequence += 1
                if remain_hour_a_day:
                   hour = remain_hour_a_day
                   remain_hour_a_day = 0.0
                else:   
                    if total_hour >= hour_a_day:
                        hour = hour_a_day
                        total_hour -= hour_a_day
                    else:
                        hour = total_hour
                        total_hour = 0.0    
                        remain_hour_a_day = hour_a_day - hour # for next lavoration
                        
                # For all lavoration create an appointment 4 hour | 4 hour a day
                current_date_text = "%s %02d:00:00" % (
                    current_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
                    start_hour, )
                    
                if not remain_hour_a_day: # no remain hour to fill
                    current_date = current_date + timedelta(days=1)
                workcenter_pool.create(cr, uid, {
                    'name': '%s [%s]' % (
                        production_proxy.name, sequence),
                    'sequence': sequence,
                    'workcenter_id': lavoration.line_id.id,
                    'date_planned': current_date_text,
                    'date_start': current_date_text, # TODO: set up by wf
                    'hour': hour,
                    'product': production_proxy.product_id.id,
                    'production_id': production_proxy.id,
                    'lavoration_id': lavoration.id,
                    'lavoration_qty': hour * (
                        production_proxy.product_qty / lavoration.duration),
                    'workers': lavoration.workers,
                    }, context=context)
                    
        #if current_date_text:            
        #    production['date_finished'] = current_date_text
        
        # Update production with time value # TODO set in lavoration write 
        #production_pool.write(cr, uid, [active_id], production, context=context)
        return True

    
    def open_lavoration(self, cr, uid, ids, context=None):
        ''' Open in calendar all lavorations for this production
        '''
        return self.open_view(
            cr, uid, ids, 'production', context=context) or {}
        
            
    def load_lavoration(self, cr, uid, ids, context=None):
        ''' Load and calculate time based on lavoration in BOM selected
        '''
        # Delete current
        lavoration_pool = self.pool.get('mrp.bom.lavoration')
        lavoration_ids = lavoration_pool.search(cr, uid, [
            ('production_id', '=', ids[0])], context=context)
        try:    
            lavoration_pool.unlink(cr, uid, lavoration_ids, context=context)
        except:
            pass # TODO
                
        # Create new from BOM 
        production_proxy = self.browse(cr, uid, ids, context=context)[0]
        for lavoration in production_proxy.bom_id.lavoration_ids:
            if lavoration.fixed:
                duration = lavoration.duration
            else:
                try:
                    duration = lavoration.duration * (
                        production_proxy.product_qty / lavoration.quantity)
                except:
                    duration = 0.0    
            lavoration_pool.create(cr, uid, {
                'production_id': ids[0],
                'phase_id': lavoration.phase_id.id,
                'level': lavoration.level,
                'fixed': lavoration.fixed,
                'duration': duration,
                'workers': lavoration.workers,
                'line_id': lavoration.line_id.id,
                'bom_id': False,                        
                }, context=context)
        return True
        
    _columns = {
        'lavoration_ids': fields.one2many('mrp.bom.lavoration',
            'production_id', 'Lavoration'),
        'scheduled_lavoration_ids': fields.one2many('mrp.production.workcenter.line',
            'production_id', 'Scheduled lavoration'),
        'worker_ids': fields.many2many('hr.employee', 'mrp_production_workcenter_employee', 'production_id', 'employee_id', 'Employee'),
        
        # For schedule lavoration:
        'schedule_from_date': fields.date(
            'From date', help="Scheduled from date to start lavorations"),
        'workhour_id':fields.many2one('hr.workhour', 'Work hour'), # TODO mand.
        }

class mrp_production_workcenter_line(orm.Model):
    ''' Extra field for workcenter line for extra info about lavoration
    '''
    _inherit = 'mrp.production.workcenter.line'
    
    _columns = {
        'lavoration_id': fields.many2one('mrp.bom.lavoration', 
            'Linked lavoration', ondelete='set null'),
        'phase_id': fields.related('lavoration_id','phase_id', type='many2one',
            relation='mrp.bom.lavoration.phase', string='Phase', store=False),
        'level': fields.related('lavoration_id','level', type='integer', string='Level'),
        'workers': fields.integer('Default workers'),
        'worker_ids': fields.many2many('hr.employee', 
            'mrp_production_workcenter_line_employee', 
            'lavoration_id', 'employee_id', 'Employee'),
        'lavoration_qty': fields.float('Lavoration qty', digits=(10, 2),
            help="Quantity lavoration"),
        'duration': fields.float('Duration', digits=(10, 2),
            help="Duration in hour:minute for lavoration of quantity piece"),
        'updated': fields.boolean('Label', required=False),    
        }

class product_product(orm.Model):
    ''' Add extra field for status report
    '''
    _name = 'product.product'
    _inherit = 'product.product'
    
    _columns = {
        'show_in_status': fields.boolean('Show in status report'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
