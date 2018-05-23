# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
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
from utility import * 


_logger = logging.getLogger(__name__)

class CreateMrpProductionWizard(orm.TransientModel):
    ''' Wizard that create a production order based on selected order lines
    '''    
    _name = "mrp.production.create.wizard"
    
    # ---------------
    # Utility funtion
    # ---------------
    def preserve_window(self, cr, uid, ids, context=None):
        ''' Create action for return the same open wizard window
        '''
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[
            ('model', '=', 'mrp.production.create.wizard'),
            ('name', '=', 'Create production order') # TODO needed?
            ], context=context)
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Wizard create production order",
            'res_model': 'mrp.production.create.wizard',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'nodestroy': True,
            }
        
    # ----------    
    # On Change:            
    # ----------    
    def onchange_schedule_date(self, cr, uid, ids, schedule_from_date, bom_id,
            days=9, context=None):
        ''' Present a little calendar based on start date
        '''
        def format_date(value):
            '''Date for columns header'''
            return "%s-%s" % (value[8:10], value[5:7])
        
        res = {'value': {}}

        if not(schedule_from_date and bom_id):
            return res
                
        # Read line info: TODO (passed to onchange??    
        try:
            wc_proxy = self.pool.get('mrp.bom').browse(
                cr, uid, bom_id, context=None)
            workcenter_id = wc_proxy.lavoration_ids[0].workcenter_id.id
            workcenter_name = wc_proxy.lavoration_ids[0].workcenter_id.name
            workers = wc_proxy.lavoration_ids[0].workers or 0
                
        except:
            pass # TODO osv.except_osv()
            res['value']['calendar'] = _('No BOM or line finded!')
            return res

        # Manage date:
        if days <= 0: # Test positive days
            res['value']['calendar'] = _('Need days > 0!')
            return res

        start_date = datetime.strptime(schedule_from_date, '%Y-%m-%d')
        to_date = (start_date + relativedelta(days=days)).strftime('%Y-%m-%d')
        calendar = {}
        
        process_pool = self.pool.get('mrp.production.workcenter.line')
        process_ids = process_pool.search(cr, uid, [
            #('workcenter_id', '=', workcenter_id),# after (for H/u total)
            ('date_planned', '>=', schedule_from_date),
            ('date_planned', '<', to_date),
            ], context=None)

        # Read process data and store in calendar
        for process in process_pool.browse(
                cr, uid, process_ids, context=context):
            key = format_date(process.date_planned)
            
            if key not in calendar:
                calendar[key] = [0.0, 0.0] # H, H/m

            if process.workcenter_id.id == workcenter_id:
                calendar[key][0] += process.hour
            calendar[key][1] += process.hour * process.workers

        row1 = ''
        row2 = ''
        header = ''
        for i in range(0, days):        
            to_date = format_date(
                (start_date + relativedelta(days=i)).strftime('%Y-%m-%d'))
            header += '<th>%s</th>' % to_date
            row1 += '<td>%s</td>' % calendar.get(to_date, ("-", "-"))[0]
            row2 += '<td>%s</td>' % calendar.get(to_date, ("-", "-"))[1]

        res['value']['calendar'] = '''
            <style>
                    .table_status {
                         border: 1px solid black;
                         padding: 3px;
                     }
                    .table_status td {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                     }
                    .table_status th {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                         background-color: grey;
                         color: white;
                     }
            </style>
                <table class='table_status'>
                    <tr><th>%s</th>%s</tr>
                    <tr><td>H.</td>%s</tr>
                    <tr><td>H./u.</td>%s</tr>
                <table>''' % (
            workcenter_name,    
            header,
            row1,
            row2,
            )            
        return res        
        
    def onchange_operation(self, cr, uid, ids, operation, product_tmpl_id, 
            context=None):
        ''' On change operation list all production open in HTML style
        '''
        res = {'value': {}}
        res['value']['other_production'] = _('<b>No production</b>')
        if not product_tmpl_id or operation not in (
                'append', 'append_reload'):
            return res
        # get product_id from template:
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('product_tmpl_id', '=' , product_tmpl_id)], context=context)
        
        if not product_ids:
            return res
            
        production_pool = self.pool.get('mrp.production')
        production_ids = production_pool.search(
            cr, uid, [('product_id', '=', product_ids[0])], # TODO only open?
                context=context)
                
        res['value']['other_production'] = _(
            '''<style>
                    .table_status {
                         border: 1px solid black;
                         padding: 3px;
                     }
                    .table_status td {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                     }
                    .table_status th {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                         background-color: grey;
                         color: white;
                     }
                </style>
                <table class='table_status'>
                <tr><th>Date</th>
                    <th>Prod.</th>
                    <th>Q.</th>                    
                </tr>''')
        for item in production_pool.browse(
                cr, uid, production_ids, context=context):
            res['value']['other_production'] += """
                <tr><td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                </tr>""" % (
                    item.date_planned[:10], 
                    #item.name, # TODO range date!!
                    item.name,
                    item.product_qty,
                    )
        else:
            res['value']['other_production'] += '</table>'
                    
        return res
        
    """def onchange_append_production(self, cr, uid, ids, production_id, 
            #oc_total, 
            context=None):
        ''' Search values for total
        ''' 
        if not production_id:
            return {}
        res = {'value': {}}
        production_pool = self.pool.get('mrp.production')
        production_proxy = production_pool.browse(
            cr, uid, production_id, context=context)
        res['value']['production_total'] = production_proxy.product_qty
        #res['value']['production_extra'] = production_proxy.extra_qty        
        #res['value']['production_oc'] = production_proxy.oc_qty        
        return res """

    #def onchange_total(self, cr, uid, ids, total, oc_total, context=None):
    #    ''' Create extra production value             
    #    ''' 
    #    #TODO also error
    #    res = {'value': {}}
    #    res['value']['extra_total'] = (total or 0.0) - (oc_total or 0.0)
    #    return res 
    
    def onchange_force_production(self, cr, uid, ids, force_production, bom_id,
            context=None):
        ''' Reset parameter or set as bom production one's
        '''
        res = {'value': {
            'item_hour': False, 'workers': False, 'workcenter_id': False}}
        if force_production:
            try:
                bom_pool = self.pool.get('mrp.bom')
                bom_proxy = bom_pool.browse(cr, uid, bom_id, context=context)
                for item in bom_proxy.lavoration_ids:
                    if item.phase_id.production_phase: # first production                         
                        res['value'].update({
                            'item_hour': item.item_hour or 0.0,
                            'workers': item.workers or False,
                            'workcenter_id': item.workcenter_id.id,
                            })
                        print res    
            except:
                pass
        return res      
                
    # --------------
    # Wizard button:
    # --------------
    def action_create_mrp_production_order(self, cr, uid, ids, context=None):
        ''' Create production order based on product_tmpl_id depend on quantity
            Redirect mrp.production form after
        '''
        if context is None:
            context = {}
           
        sol_ids = context.get("active_ids", [])   

        # Wizard proxy:
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Pool used:
        production_pool = self.pool.get('mrp.production')
        sol_pool = self.pool.get('sale.order.line')
                
        # Not used for now:
        product_id = get_product_from_template(
            self, cr, uid, wiz_proxy.product_tmpl_id.id, context=context)
            
        # Context dict for pass parameter to create lavoration procedure:
              
        context['mrp_data'] = {
            'bom_id': wiz_proxy.bom_id.id, 
            'operation': wiz_proxy.operation, # create or append
            'total': wiz_proxy.total,
            # Not mandatory in append:
            'schedule_from_date': wiz_proxy.schedule_from_date,
            'workhour_id': wiz_proxy.workhour_id.id, 
            'mode': wiz_proxy.operation, # TODO split!!!
            }            
        if wiz_proxy.force_production:
            # Use forced value (now mandatory)
            context['mrp_data'].update({
                'item_hour': wiz_proxy.item_hour,
                'workers': wiz_proxy.workers,
                'workcenter_id': wiz_proxy.workcenter_id.id,                
                # Not used for now:
                # fixed
                # phase_id
                })
        else:
            # Call onchange function for calculate from BOM:
            try:
                context['mrp_data'].update(
                    self.onchange_force_production(cr, uid, ids, True, 
                        wiz_proxy.bom_id.id, context=context)['value'])
            except:
                raise osv.except_osv(
                    _('Error'),
                    _('Error reading parameter in BOM (for lavoration)'))

        if wiz_proxy.operation == 'append':
            # Append extra parameter:
            context['mrp_data'].update({
                'append_production_id':wiz_proxy.production_id.id,
                'append_product_qty': wiz_proxy.production_id.product_qty,
                })
        else:        
            context['mrp_data'].update({
                'append_production_id': False,
                'append_product_qty': False,
                })        

        # Create a production order:
        if wiz_proxy.operation in ('create'):
            # Create lavoration:
            p_id = production_pool.create(cr, uid, {
                # Production data:
                'name': self.pool.get(
                    'ir.sequence').get(cr, uid, 'mrp.production'),
                'date_planned': context['mrp_data']['schedule_from_date'],#TODO right?
                'user_id': uid,
                #'order_line_ids': [(6, 0, context.get("active_ids", []))],
                'product_qty': context['mrp_data']['total'], # sum(order line)
                # Keep for mandatory fields in production
                'bom_id': wiz_proxy.bom_id.id,

                # Not necessary for this installation:
                'product_id': product_id,
                'product_uom': wiz_proxy.product_id.uom_id.id,                    
                }, context=context)

            # Update line:
            sol_pool.write(cr, uid, sol_ids, {
                'mrp_id': p_id,
                'mrp_unlinked': False,
                }, context=context)

        else: # 'append'
            p_id = context['mrp_data']['append_production_id']

            # Add sale order line to production:
            sol_pool.write(
                cr, uid, sol_ids, {
                    'mrp_id': p_id,
                    'mrp_unlinked': False,
                    }, context=context)
                    
            # Udate start date:        
            if context['mrp_data']['schedule_from_date']:
                production_pool.write(               
                    cr, uid, p_id, {
                        'date_planned': context['mrp_data'][
                            'schedule_from_date'],
                        }, context=context)

        # Reforce total from sale order line:
        production_pool.recompute_total_from_sol(
            cr, uid, [p_id], context=context) 

        # Force (re)schedule (create / append):
        production_pool.create_lavoration_item(# and workcenter line
            cr, uid, [p_id], mode='create', context=context)

        return return_view(
            self, cr, uid, p_id, 'mrp.mrp_production_form_view', 
            'mrp.production', context=context) 

    # -----------------
    # Default function:        
    # -----------------
    def default_oc_list(self, cr, uid, field, context=None):
        ''' Get list of order for confirm as default
            context: used for select product or family (grouping clause)
        '''
        import pdb; pdb.set_trace()
        if context is None:
            context = {}

        sol_pool = self.pool.get('sale.order.line')
        ids = sol_pool.search(cr, uid, [
            ('id', 'in', context.get("active_ids", [])),
            ], context=context)
        sol_browse = sol_pool.browse(cr, uid, ids, context=context) 
        
        if context.get('grouping', 'product') == 'product':
            ref_field = 'product_id'
        else:
            ref_field = 'family_id'    

        default = {
            "list": _("""
                <style>
                    .table_bf {
                         border: 1px solid black;
                         padding: 3px;
                     }
                    .table_bf td {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                     }
                    .table_bf th {
                         border: 1px solid black;
                         padding: 3px;
                         text-align: center;
                         background-color: grey;
                         color: white;
                     }
                </style>
                <table class='table_bf'>
                <tr class='table_bf'>
                    <th>OC</th>
                    <th>Q.</th>
                    <th>Deadline</th>
                </tr>"""), 
            "is_error": False, 
            #"oc_total": 0.0, 
            "total": 0.0, 
            "product": False, 
            "from_deadline": False, 
            "to_deadline": False, 
            "bom": False,
            "error": "", #TODO
            "warning": "", #TODO
            }             
        res = default.get(field, False)        
        old_product_id = False     
        
        try:
            if field == "template": # so template
                if ref_field == 'product_id':
                    return sol_browse[0].product_id.product_tmpl_id.id
                else: # family
                    return sol_browse[0].family_id.id                
        except:
            return False
        try:
            if field == "product": # so template
                if ref_field == 'product_id':
                    return sol_browse[0].product_id.id
                else: # family
                    return get_product_from_template(
                        self, cr, uid, sol_browse[0].family_id.id, 
                        context=context)
        except:
            return False
            
        try:
            if field == "bom":        
                if ref_field == 'product_id':
                    tmpl_id = sol_browse[0].product_id.product_tmpl_id.id
                else: # family
                    tmpl_id = sol_browse[0].family_id.id                

                # Search BOM for template:
                item_ids = self.pool.get("mrp.bom").search(
                    cr, uid, [(
                        'product_tmpl_id', '=', tmpl_id), ], context=context)
                if item_ids:
                    return item_ids[0]
                else: 
                    return False    
        except:
            return False    

        for item in sol_browse:
            if old_product_id == False:
                old_product_id = item.__getattribute__(ref_field).id
                
            # Test function mode:
            if field == "list":
                if item.__getattribute__(ref_field).id != old_product_id:
                    res = "Error! Choose order line that are of one product ID"
                    break                                    
                         
                res += """
                    <tr>
                        <td>%s [%s] </td>
                        <td>%s</td>
                        <td>%s</td>
                    </tr>""" % (
                        item.order_id.name,
                        item.sequence,
                        item.product_uom_qty,
                        "%s/%s/%s" % (
                            item.date_deadline[8:10],
                            item.date_deadline[5:7],
                            item.date_deadline[:4],
                            ) if item.date_deadline else _("Not present!")
                        )
            elif field == "error":
                if item.__getattribute__(ref_field).id != old_product_id:
                    return True
            elif field in ("total"): #"oc_total", 
                res += item.product_uom_qty or 0.0
            elif field in ("from_deadline", "to_deadline"):
                if not res:
                    res = item.date_deadline
                if field == "from_deadline":
                    if item.date_deadline < res:
                        res = item.date_deadline
                else: # to_deadline
                    if item.date_deadline > res:
                        res = item.date_deadline
        else:
            if field == "list":
                res += "</table>" # close table for list element
        return res
   
    def _get_wh_default(self, cr, uid, context=None):
        ''' Get default from data if present 
            TODO >> maybe bettere with a boolean (for deletion)
        '''
        try:
            res = self.pool.get('ir.model.data').xmlid_to_res_id(
                cr, uid, 'hr_workhour.hr_workhour_normal') or False
            return res    
        except:
            return False    
            
    _columns = {
        'name': fields.text('OC line', readonly=True),

        # Total block (current order)
        'extra_total': fields.float(
            'Extra total', digits=(16, 2), readonly=True),
        #'oc_total': fields.float(
        #    'OC total', digits=(16, 2), readonly=True),
        'total': fields.float(
            'Total (current block)', digits=(16, 2), required=True,
            help='Total only for this block, if append will be integrated'),

        # Total production to update (only info)
        #'production_extra': fields.float(
        #    'Production: Extra', readonly=True, digits=(16, 2), ),
        #'production_oc': fields.float(
        #    'Production: OC', readonly=True, digits=(16, 2), ),
        'production_total': fields.float(
            'Production: Total', readonly=True, digits=(16, 2), ),

        # Production corrections:
        'force_production': fields.boolean('Force production'),
        'item_hour': fields.float(
            'Item per hour', digits=(16, 2),
            help="For generare lavoration (required when BOM not present"),
        'workers': fields.integer('Workers'),

        'product_id': fields.many2one(
            'product.product', 'Product/Family'), # only for filter BOM
        'product_tmpl_id': fields.many2one(
            'product.template', 'Mod. Product/Family', required=True),
        'production_id': fields.many2one(
            'mrp.production', 'Production'),
        'bom_id': fields.many2one('mrp.bom', 'BOM'),

        'from_deadline': fields.date('From deadline', 
            help='Min deadline found in order line!',
            readonly=True),
        'to_deadline': fields.date('To deadline', 
            help='Max deadline found in order line!',
            readonly=True),

        # Force block:
        'schedule_from_date': fields.date(
            'From date', help="Scheduled from date to start lavorations"),
        'workhour_id':fields.many2one('hr.workhour', 'Work hour'), # TODO mand.
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Workcenter line'), 

        # Error control:
        'is_error': fields.boolean('Is error'),
        'other_production': fields.text(
            'Other production', 
            help="Production open on line of this production", readonly=True),
        'error': fields.text('Error', readonly=True),
        'warning': fields.text('Warning', readonly=True),
        'calendar': fields.text('Calendar', readonly=True),
        'operation': fields.selection([
            ('create', 'Create'),
            ('append', 'Append'),
            ], 'Operation', select=True, required=True),
        }
        
    _defaults = {
        'name':  lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "list", context=c),
        #'all_in_one': lambda *a: False,
        'is_error': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "error", context=c),
        #'oc_total': lambda s, cr, uid, c: s.default_oc_list(
        #    cr, uid, "oc_total", context=c),        
        'total': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "total", context=c),        
        'product_id': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "product", context=c),        
        'product_tmpl_id': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "template", context=c),        
        'bom_id': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "bom", context=c),        
        'from_deadline': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "from_deadline", context=c),        
        'to_deadline': lambda s, cr, uid, c: s.default_oc_list(
            cr, uid, "to_deadline", context=c),        
        'operation': lambda *x: 'create',
        'workhour_id': lambda s, cr, uid, ctx: s._get_wh_default(cr, uid, ctx),
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
