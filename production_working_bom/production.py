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
    _inherit = 'res.company'
    
    # Utility:
    def get_hour_parameters(
            self, cr, uid, company_id=False, context=None):
        ''' Read element with company_id or passed 
        '''
        if not company_id:
            company_id = self.search(cr, uid, [], context=context)[0]
        elif type(company_id) in (list, tuple):
            company_id = company_id[0]
        return self.browse(cr, uid, company_id, context=context)
        
        
    _columns = {
        'start_hour': fields.integer('Start hour', 
            help='Start hour for create working process'),

        # Statistic data for color report depend on cases:
        'work_hour_day': fields.integer('Work hour day', 
            help='Normal work hour for one man in a day'),
        'extra_hour_day': fields.integer('Extra hour day', 
            help='Normal extra work for one man in a day'),    
        'employee': fields.integer('# employee', 
            help='Medium number of employee this company for work'),
        }
    
    _defaults = {
        'workhour_day': lambda *x: 8.0,
        'extra_hour_day': lambda *x: 1.0,
        }    

#class mrp_workcenter(orm.Model):
#    ''' Add fields for report in workcenter
#    '''
#
#    _inherit = 'mrp.workcenter'
#    
#    _columns = {
#        'ordinary_hour': fields.integer('Ordinary hour', 
#            help='Normal work hours'),
#        'extra_hour': fields.integer('Ordinary hour', 
#            help='Extra work max hours'),
#        }

class mrp_bom_lavoration(orm.Model):
    ''' Add relation fields (use same element in BOM and in production)
    '''

    _inherit = 'mrp.bom.lavoration'

    # -------
    # Button:    
    # -------
    def open_lavoration_wc(self, cr, uid, ids, context=None):
        ''' Open in calendar all lavorations for this workcenter
        '''
        return self.pool.get('mrp.production').open_view(
            cr, uid, ids, 'workcenter', context=context) or {}

    # ----------------
    # Function fields:
    # ----------------
    def _function_get_wc_data(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate totals depend on wc lines 
        '''    
        res = {}
        for lavoration in self.browse(cr, uid, ids, context=context):
            # Initial setup:
            res[lavoration.id] = {}            
            
            res[lavoration.id]['total_number'] = len(
                lavoration.scheduled_ids)
            res[lavoration.id]['total_duration'] = 0.0
            res[lavoration.id]['total_product'] = 0.0
            
            for wc in lavoration.scheduled_ids:
                res[lavoration.id]['total_duration'] += wc.hour
                res[lavoration.id]['total_product'] += wc.lavoration_qty
        return res
        
    _columns = {
        # ----------------------------
        # Extra fields for lavoration:
        # ----------------------------
        # Link
        'production_bom_id': fields.many2one('mrp.bom', 'Production BOM', 
            ondelete='set null'),
        'production_id': fields.many2one('mrp.production', 'Production', 
            ondelete='cascade'),            
        'workhour_id':fields.many2one('hr.workhour', 'Work hour', 
            ondelete='set null'),
        'item_hour': fields.float('Item x hour', digits=(10, 2),
            help="Number of item per hour, for possibile recalc operation"),            
        # Splitted information:    
        'splitted': fields.boolean('Splitted', 
            help='This lavoration is a splitted block, else original create'),
        'schedule_from_date': fields.date(
            'From date', help="Scheduled from date to start lavorations"),

        # --------------------------------------    
        # Calculated total from workcenter_line:    
        # --------------------------------------    
        'total_duration': fields.function(
            _function_get_wc_data, method=True, type='float', 
            string='Total duration', digits=(10,2), store=False, multi='wc',
            help='Total time of this operation phase'), 
        'total_product': fields.function(
            _function_get_wc_data, method=True, type='float', 
            string='Total product', digits=(10,2), store=False, multi='wc',
            help='Total quantity of product for this operation phase'), 
        'total_number': fields.function(
            _function_get_wc_data, method=True, type='integer', 
            string='Total number', store=False, multi='wc',
            help='Total # of child lavorarion for this operation phase'),             
                        
        #'total_duration': fields.float('Duration', digits=(10, 2),
        #    help="Duration hour:minute for lavoration of quantity piece"),

        # TODO move in another module after DEMO    
        #'real_duration': fields.float('Duration', digits=(10, 2),
        #    help="Real duration hour:minute for lavoration of quantity piece")
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
    def write_sequence_order_line(self, cr, uid, ids, context=None):
        ''' Recompute total order from sale order line (one record of mrp)
        '''
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        sol_pool = self.pool.get('sale.order.line')
        
        i = 0
        for line in mrp_proxy.order_line_ids:
            i += 1 
            sol_pool.write(cr, uid, line.id, {
                'mrp_sequence': i,
                }, context=context)
        return True

    def recompute_total_from_sol(self, cr, uid, ids, context=None):
        ''' Recompute total order from sale order line (one record of mrp)
        '''
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        product_qty = sum(
            [item.product_uom_qty for item in mrp_proxy.order_line_ids])
        
        self.write_sequence_order_line(cr, uid, ids, context=context)    
        return self.write(cr, uid, ids[0], {
            'product_qty': product_qty,
            }, context=context)
        
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

        # -----------------------
        # Return view parameters:
        # -----------------------
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
        # production_working_bom.
        # mrp_production_workcenter_line_calendar_lavoration_view
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
            'name': name, 'view_type': view_type, 'view_mode': view_mode,
            'res_model': model, 'res_id': res_id, 'view_id': view_id,
            'views': views, 'domain': domain, 'context': view_context,
            'type': 'ir.actions.act_window'}

    def create_wc_from_lavoration(self, cr, uid, order_id, context=None):
        ''' Create sub workcenter from lavoration
            @param self: instance of class
            @param cr: cursor
            @param uid: user ID
            @param order_id: mrp order passed used for create all wc 
                from lavoration
            @param context: extra parameters
        '''
        # TODO read all lavoration

        # TODO load a date list for leave days >> need a module for this
        
        # Check possibly lavoration present:
        
        # TODO Compute total (more / less todo) hour

        start_hour = 7.0
        
        # Production data to update after:
        min_date = False
        max_date = False

        # Pools used:
        wc_pool = self.pool.get('mrp.production.workcenter.line')
        
        # ---------------------------------------------------------------------
        #                  Create workcenter line from lavorations:
        # ---------------------------------------------------------------------        
        mrp_proxy = self.browse(cr, uid, order_id, context=context)
        for lavoration in mrp_proxy.lavoration_ids:
            # -----------------------------------
            # Workhour for this lavoration phase:
            # -----------------------------------
            workhour = {}
            for item in lavoration.workhour_id.day_ids: # wh now in lavoration
                # int for '0' problems on write operation:
                workhour[int(item.weekday)] = item.hour 
                
            # Init variables:
            total_hour = lavoration.duration # total hour to split                
            remain_hour_a_day = 0.0 # for multiblock element
            max_sequence = 0
            schedule_from_date = lavoration.schedule_from_date # default:
            
            # For all lav. create an appointment X hour a day
            current_date = datetime.strptime(
                schedule_from_date, DEFAULT_SERVER_DATE_FORMAT)
            
            # Leave loop for next developing (now only one line=production)
            while total_hour > 0.0:
                # Not work days for workhour plan:
                wd = current_date.weekday()
                if wd not in workhour: 
                    current_date = current_date + timedelta(days=1)
                    continue
                    
                max_sequence += 1
                hour_a_day = workhour.get(wd, 0.0) # total H to work this day
                
                # Check remain from another phase:
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
                        remain_hour_a_day = hour_a_day - hour 
                        
                # For all lav. create an appointment X hour a day
                current_date_text = "%s %02d:00:00" % (
                    current_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
                    start_hour, )
                
                # Read data for production (write after)    
                if not min_date:
                    min_date = current_date_text[10]
                if not max_date or max_date < current_date_text[:10]:
                    max_date = current_date_text[:10]                                
                    
                if not remain_hour_a_day: # no remain hour to fill
                    current_date = current_date + timedelta(days=1)

                wc_pool.create(cr, uid, {
                    'name': '%s [%s]' % (
                        mrp_proxy.name, max_sequence),
                    'sequence': max_sequence,
                    'workcenter_id': lavoration.line_id.id,
                    'date_planned': current_date_text,
                    'date_start': current_date_text,
                    'phase_id': lavoration.phase_id.id,
                    'product': mrp_proxy.product_id.id,
                    'production_id': mrp_proxy.id,
                    'lavoration_id': lavoration.id,

                    # Data field that will be related on lavoration:
                    'hour': hour,
                    'lavoration_qty': round( # Statistic m(x):
                        hour * lavoration.item_hour)
                        #(mrp_proxy.product_qty / lavoration.duration), 0),
                    #'workers': lavoration.workers, # related for now                    
                    }, context=context)
                    
        # TODO Write some date in production start / stop?
        # Write data in production from lavoration and workcenter:
        # TODO 
        '''self.write(cr, uid, ids, {
            '': max_date,
            '': min_date,
            }, context=context)'''
        return True
        
    def create_lavoration_item(self, cr, uid, ids, mode='create', 
            context=None):
        ''' Create lavoration item (case: new, append, splitted), use a 
            procedure for generate all workcenter line
            @param cr: cursor
            @param self: instance of class
            @param uid: user ID
            @param ids: mrp order 
            @param context: extra parameters
                Force value instead of bom:
                    force_production_hour > force hour not bom
                    force_production_employee > force employee not bom
                    force_workcenter > force workcenter not bom

                Force split element:
                    splip_data > dict for pass split parameters

            @param mode:
                'create':
                    order_line_ids >> used for get all totals
            
                'update':
                    delete all and re-create
                
                'split':
                    context:
                        split_data: {
                            # Parameters:
                            from_date: 
                            wc_id: production line from to move
                        
                            # Record value:
                            'bom_id' 
                                get: level, phase_id, fixed, workers, item_hour, 
                                     line_id
                            'duration'
                            'quantity'
                            'item_hour' (forced)
                            'workers' (forced)
                            }                        
        '''
        if context is None:
            context = {}

        # ---------------------------------------------------------------------
        #                       Parameters to load:
        # ---------------------------------------------------------------------
        # Variables:
        start_hour = 7.0 # TODO parametrize GMT       

        # Proxy element:
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Context elements:
        force_production_hour = context.get(
            'force_production_hour', False)
        force_production_employee = context.get(
            'force_production_employee', False)   
        force_workcenter = context.get(
            'force_workcenter', False)   
        split_data = context.get(
            'split_data', {})   

        # Pool used:
        wc_pool = self.pool.get('mrp.production.workcenter.line')
        lavoration_pool = self.pool.get('mrp.bom.lavoration')

        # ---------------------------------------------------------------------
        #                            PROCEDURE:
        # ---------------------------------------------------------------------
        if mode in ('create', 'append'):
            # Remove lavoration and workcenter line
            old_lavoration_ids = lavoration_pool.search(cr, uid, [
                ('production_id', '=', ids[0])], context=context)
            try:    
                lavoration_pool.unlink(
                    cr, uid, old_lavoration_ids, context=context)
            except:
                pass # TODO
            # TODO test deletion of wc line
            # TODO delete only workcenter line not confirmed??
            
            # ------------------------------------
            # Create lavoration from BOM elements:
            # ------------------------------------
            for lavoration in mrp_proxy.bom_id.lavoration_ids:
                if lavoration.fixed:
                    duration = lavoration.duration
                else:
                    try: 
                        # K (coeff) could be forced:
                        item_hour = force_production_hour or (
                            lavoration.quantity / lavoration.duration)
                        duration = mrp_proxy.product_qty / item_hour
                    except:
                        duration = 0.0                        
            # Workers (could be forced):
            workers = force_production_employee or lavoration.workers or 0

            # Check mandatory elements:
            if not mrp_proxy.workhour_id:
                raise osv.except_osv(_('Error'), _('No work hour type setted!'))
            if not mrp_proxy.schedule_from_date:
                raise osv.except_osv(_('Error'), _('No start date for schedule!'))
            lavoration_pool.create(cr, uid, {
                # Record data:
                #'create_date',
                'schedule_from_date': mrp_proxy.schedule_from_date,
                'production_id': ids[0],
                'splitted': False, # original creation
                'workhour_id': mrp_proxy.workhour_id.id, # same as mrp
                
                # BOM:
                #'bom_id': mrp_proxy.bom_id.id, # TODO remove (bom line)
                'production_bom_id': mrp_proxy.bom_id.id,
                'level': lavoration.level,
                'phase_id': lavoration.phase_id.id,
                'line_id': force_workcenter or lavoration.line_id.id,
                'fixed': lavoration.fixed,
                'workers': workers,

                # BOM and sale order
                'item_hour': item_hour,
                # Note: workcenter creation depend from this:
                'duration': duration, # sum(sale order line)
                #'quantity': ,# TODO total from sale order lines
                }, context=context)

        elif mode in ('split'):
            pass # TODO split case
        
        # ----------------------------------------
        # Create workcenter line under lavoration:        
        # ----------------------------------------
        self.create_wc_from_lavoration(cr, uid, ids, context=context)
        return True        
        
    # -------------
    # Button event:
    # -------------
    def reschedule_lavoration(self, cr, uid, ids, context=None):
        ''' Force reload all lavoration-workcenter line
        '''
        # Recompute total from sale order line:
        self.pool.get('mrp.production').recompute_total_from_sol(
            cr, uid, ids, context=context)
        return self.create_lavoration_item(cr, uid, ids, mode='create', 
            context=context)
    
    def open_lavoration(self, cr, uid, ids, context=None):
        ''' Open in calendar all lavorations for this production
        '''
        return self.open_view(
            cr, uid, ids, 'production', context=context) or {}
        
    _columns = {
        'lavoration_ids': fields.one2many('mrp.bom.lavoration',
            'production_id', 'Lavoration'),
        'scheduled_lavoration_ids': fields.one2many(
            'mrp.production.workcenter.line',
            'production_id', 'Scheduled lavoration'),
        'worker_ids': fields.many2many('hr.employee', 
            'mrp_production_workcenter_employee', 'production_id', 
            'employee_id', 'Employee'),
        
        # For schedule lavoration (detault parameter of production:
        # NOTE: all this parameter are also written in lavoration
        'schedule_from_date': fields.date(
            'From date', help="Scheduled from date to start lavorations"),
        'workhour_id':fields.many2one('hr.workhour', 'Work hour', 
            required=True),
        }

class mrp_production_workcenter_line(orm.Model):
    ''' Extra field for workcenter line for extra info about lavoration
    '''
    _inherit = 'mrp.production.workcenter.line'
    
    _columns = {
        'lavoration_id': fields.many2one('mrp.bom.lavoration', 
            'Linked lavoration', ondelete='cascade'),

        # Related fields:
        'phase_id': fields.related('lavoration_id','phase_id', type='many2one',
            relation='mrp.bom.lavoration.phase', string='Phase', store=False),            
        'level': fields.related('lavoration_id', 'level', type='integer', 
            string='Level'),
        'workers': fields.related('lavoration_id', 'workers', type='integer', 
            string='Workers'),
        #'workers': fields.integer('Default workers'), # TODO not used?
         
        # Lavoration data:                
        'worker_ids': fields.many2many('hr.employee', # TODO used?
            'mrp_production_workcenter_line_employee', 
            'lavoration_id', 'employee_id', 'Employee'),
        'lavoration_qty': fields.float('Lavoration qty', digits=(10, 2),
            help="Quantity lavoration"),
        'duration': fields.float('Duration', digits=(10, 2),
            help="Duration in hour:minute for lavoration of quantity piece"),

        'updated': fields.boolean('Updated'),
        }

class product_product(orm.Model):
    ''' Add extra field for status report
    '''
    _inherit = 'product.product'
    
    _columns = {
        'show_in_status': fields.boolean('Show in status report'),
        }

class mrp_bom_lavoration(orm.Model):
    ''' Add relation fields (use same element in BOM and in production)
    '''
    _inherit = 'mrp.bom.lavoration'
    
    _columns = {
        # workcenter depend on lavoration element
        'scheduled_ids': fields.one2many('mrp.production.workcenter.line',
            'lavoration_id', 'Scheduled lavorations'), 
        }       
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
