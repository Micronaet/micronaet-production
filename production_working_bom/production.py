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
        'work_hour_day': fields.integer('Worh hour day', 
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

    _columns = {
        'production_id': fields.many2one('mrp.production', 'Production', 
            ondelete='cascade'),            
        'total_duration': fields.float('Duration', digits=(10, 2),
            help="Duration hour:minute for lavoration of quantity piece"),

        # TODO move in another module after DEMO    
        'real_duration': fields.float('Duration', digits=(10, 2),
            help="Real duration hour:minute for lavoration of quantity piece"),
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
        # production_working_bom.mrp_production_workcenter_line_calendar_lavoration_view
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
    def schedule_lavoration(self, cr, uid, ids, context=None):
        ''' Schedule activities (or update current scheduled)
            This procedure could be used also for move some lavoration passing            
            in context 'move_parameters' dict key with:
            > lavoration_ids list of current lavoration to move:
            > new_date: new date to move
            > workhour_id: new workhour plan
            > workcenter_id: new workcenter line
            > workers: new number of workers
            > bom_id: new bom parameters # TODO            
        '''
        if context is None: 
            context = {}
        
        # Check move operation if present:
        move_parameters = context.get('move_parameters', False)
        
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Load information for lavoration:
        workcenter_pool = self.pool.get('mrp.production.workcenter.line')

        # Parameters to load :            
        start_hour = 7.0 # TODO parametrize GMT
            
        # TODO load a date list for leave days >> need a module for this
        
        # Force load of lavoration from bom (delete all phase present):
        self.load_lavoration(cr, uid, ids, context=context)

        # Get day of week hour totals
        workhour = {}
 
        if not mrp_proxy.workhour_id:
            raise osv.except_osv(_('Error'), _('No work hour type setted!'))
        if not mrp_proxy.schedule_from_date:
            raise osv.except_osv(_('Error'), _('No start date for schedule!'))

        for item in mrp_proxy.workhour_id.day_ids:
            # use int for '0' problems on write operation:
            workhour[int(item.weekday)] = item.hour 
                    
        # ---------------------------------------------------------------------
        #              Delete lavoration not confirmed
        # ---------------------------------------------------------------------
        lavoration_pool = self.pool.get('mrp.production.workcenter.line')
        lavoration_ids = lavoration_pool.search(cr, uid, [
            ('production_id', '=', ids[0])], context=context)
        # TODO ^^^^ search only not confirmed or closed ^^^^^^
        # TODO manage error vvvvvvvv
        lavoration_pool.unlink(cr, uid, lavoration_ids, context=context)
        
        # ---------------------------------------------------------------------
        #               Check possibly lavoration present:
        # ---------------------------------------------------------------------
        # TODO Compute total (more / less todo) hour
        total_scheduled = {} # Dict for phase (currently only one)
        max_date = False
        max_sequence = 0
        last_lavoration_hour = 0.0
        for lavoration in mrp_proxy.scheduled_lavoration_ids:
            # Max number of sequence:
            if max_sequence < lavoration.sequence:
                max_sequence = lavoration.sequence
                
            # Save max date for start point:
            if not max_date or max_date < lavoration.date_start[:10]:
                max_date = lavoration.date_start[:10]            
    
            # Save total for phase for test create or delete hour    
            if lavoration.lavoration_id.id not in total_scheduled:
                total_scheduled[lavoration.phase_id.id] = lavoration.hour
            else:
                total_scheduled[lavoration.phase_id.id] += lavoration.hour
        else: # save last total
            try:
                last_lavoration_hour = lavoration.hour # last or error        
            except:
                last_lavoration_hour = 0.0

        # ---------------------------------------------------------------------
        #            Init counters depend also on previous loop
        # ---------------------------------------------------------------------
        # Parse time for delta operations:
        if max_date: # take max in lavorations (TODO + 1?)
            current_date = datetime.strptime(
                max_date, DEFAULT_SERVER_DATE_FORMAT)
        else: # take from production
            current_date = datetime.strptime(
                mrp_proxy.schedule_from_date, DEFAULT_SERVER_DATE_FORMAT)
        
        # ---------------------------------------------------------------------
        #                      Create lavorations:
        # ---------------------------------------------------------------------
        # Start loop:
        for lavoration in mrp_proxy.lavoration_ids:
            total_hour = (
                lavoration.duration - # Total
                total_scheduled.get(lavoration.phase_id.id, 0.0) # - Scheduled
                )
            # TODO To delete elements!!! remove lavoration or reduce
            
            # TODO Check if last day there's less hour to create (or integrate!!)
            #wd = current_date.weekday()
            #if last_lavoration_hour:
            #    remain_hour_a_day = last_lavoration_hour - workhour.get(wd, 0.0)
            remain_hour_a_day = 0.0
            
            # Leave loop for next developing (now only one line=production)
            while total_hour > 0.0:
                # Not work days for workhour plan:
                wd = current_date.weekday()
                if wd not in workhour: 
                    current_date = current_date + timedelta(days=1)
                    continue
                    
                max_sequence += 1
                hour_a_day = workhour.get(wd, 0.0) # total H to work this day
                if remain_hour_a_day: # for add another phase (not used yet)
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
                    
                if not remain_hour_a_day: # no remain hour to fill
                    current_date = current_date + timedelta(days=1)

                workcenter_pool.create(cr, uid, {
                    'name': '%s [%s]' % (
                        mrp_proxy.name, max_sequence),
                    'sequence': max_sequence,
                    'workcenter_id': lavoration.line_id.id,
                    'date_planned': current_date_text,
                    'date_start': current_date_text,
                    'hour': hour,
                    'phase_id': lavoration.phase_id.id,
                    'product': mrp_proxy.product_id.id,
                    'production_id': mrp_proxy.id,
                    'lavoration_id': lavoration.id,
                    'workers': lavoration.workers,

                    # Statistic m(x):
                    'lavoration_qty': round(
                        hour * (
                        mrp_proxy.product_qty / lavoration.duration), 0),
                    }, context=context)
        # TODO Write some date in production start / stop?                    
        return True
    
    def open_lavoration(self, cr, uid, ids, context=None):
        ''' Open in calendar all lavorations for this production
        '''
        return self.open_view(
            cr, uid, ids, 'production', context=context) or {}
        
    def load_lavoration(self, cr, uid, ids, context=None):
        ''' Load and calculate time based on lavoration in BOM selected
            force mechanism for hour and employee could be generated with
            context parameters: force_production_hour and
            force_production_employee
        '''
        if context is None:
            context = {}
        
        # Read parameter if present:
        force_production_hour = context.get(
            'force_production_hour', False)   
        force_production_employee = context.get(
            'force_production_employee', False)   
    
        # Delete current
        lavoration_pool = self.pool.get('mrp.bom.lavoration')
        lavoration_ids = lavoration_pool.search(cr, uid, [
            ('production_id', '=', ids[0])], context=context)
        try:    
            lavoration_pool.unlink(cr, uid, lavoration_ids, context=context)
        except:
            pass # TODO

        # Create new from BOM 
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        for lavoration in mrp_proxy.bom_id.lavoration_ids:
            if lavoration.fixed:
                duration = lavoration.duration
            else:
                try: # K could be forced:
                    k = force_production_hour or (
                        lavoration.quantity /lavoration.duration )
                    duration = mrp_proxy.product_qty / k
                except:
                    duration = 0.0    
                    
            # Workers (could be forced):
            workers = force_production_employee or lavoration.workers or 0
            
            lavoration_pool.create(cr, uid, {
                'production_id': ids[0],
                'phase_id': lavoration.phase_id.id,
                'level': lavoration.level,
                'fixed': lavoration.fixed,
                'duration': duration,
                'workers': workers,
                'line_id': lavoration.line_id.id,
                'bom_id': False,                        
                }, context=context)
        return True
        
    _columns = {
        'lavoration_ids': fields.one2many('mrp.bom.lavoration',
            'production_id', 'Lavoration'),
        'scheduled_lavoration_ids': fields.one2many(
            'mrp.production.workcenter.line',
            'production_id', 'Scheduled lavoration'),
        'worker_ids': fields.many2many('hr.employee', 
            'mrp_production_workcenter_employee', 'production_id', 
            'employee_id', 
            'Employee'),
        
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
        'level': fields.related('lavoration_id','level', type='integer', 
            string='Level'),
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
