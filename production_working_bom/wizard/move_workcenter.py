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
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
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

class mrp_production_schedulation_wizard(orm.TransientModel):
    ''' Wizard for re-schedule production depend on lavorations time
    '''
    _name = "mrp.production.schedulation.wizard"
    _description = "Production schedule wizard"

    # Wizard button:
    def action_schedule(self, cr, uid, ids, context=None):
        ''' Schedule activities
        '''
        if context is None: 
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        active_id = context.get('active_id', False)
        if not active_id:
            return False # TODO
        
        # Load information for lavoration:
        workcenter_pool = self.pool.get('mrp.production.workcenter.line')
        production_pool = self.pool.get('mrp.production')
        production_proxy = production_pool.browse(cr, uid, active_id, 
            context=context) # single record

        # Parameters:            
        max_day = 5 # < saturday
        hour_a_day = 8.0 # work hour per day   # TODO parametrize
        start_hour = 7.0 # # GMT               # TODO parametrize
        deadline = wiz_proxy.deadline or False
        schedule_type = wiz_proxy.type
        
        if schedule_type == 'hour_10':
            hour_a_day = 10.0
        elif schedule_type == 'with_saturday':
            max_day = 6
        #elif schedule_type == 'work_week':
        #    max_day = 5
        #else:
        #    pass # TODO error    
        
        current_date = datetime.strptime(
            wiz_proxy.from_date, DEFAULT_SERVER_DATE_FORMAT)
        #production = {
        #    'date_start': wiz_proxy.from_date, }
        sequence = 0
        remain_hour_a_day = 0.0
        i = 0
        current_date_text = False
        for lavoration in production_proxy.lavoration_ids:
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
                    'lavoration_qty': round(
                        hour * (
                            production_proxy.product_qty / 
                            lavoration.duration)), 2),
                    'workers': lavoration.workers,
                    }, context=context)
                    
        #if current_date_text:            
        #    production['date_finished'] = current_date_text
        
        # Update production with time value # TODO set in lavoration write 
        #production_pool.write(cr, uid, [active_id], production, context=context)
        return True

    _columns = {
        'from_date': fields.date('From date', required=True),
        'deadline': fields.date('Deadline'),        
    }           
    
    _defaults = {
        'type': lambda *x: 'work_week',
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
