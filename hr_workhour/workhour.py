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

# python represent weekday starting from 0 = Monday
week_days = [
    ('mo', 'Monday'),  
    ('tu', 'Tuesday'),     
    ('we', 'Wednesday'),     
    ('th', 'Thursday'),     
    ('fr', 'Friday'),     
    ('sa', 'Saturday'),     
    ('su', 'Sunday'),
    ]

class HrEmployeeWorkhour(orm.Model):
    ''' Manage workhour plan as employee contract
    '''    
    _name = 'hr.employee.workhour'
    _description = 'Workhour plan'
    
    _columns = {
        'name': fields.char('Name', size=64),
        'note': fields.text('Note'),
        }

class HrEmployeeWorkhourLine(orm.Model):
    ''' Manage workhour plan line
    '''    
    _name = 'hr.employee.workhour.line'
    _description = 'Workhour plan line'
    
    _columns = {
        'name': fields.float('Tot. hours', required=True, digits=(4, 2)),
        'week_day':fields.selection(week_days,'Week day', select=True),
        'workhour_id':fields.many2one(
            'hr.employee.workhour', 'Plan', ondelete='cascade'),
        }
        
    _defaults = {
        'name': lambda *x: 8.0,
        }    

class HrEmployeeWorkhour(orm.Model):
    ''' Manage workhour plan as employee contract
    '''    
    _inherit = 'hr.employee.workhour'

    _columns = {
        'line_ids': fields.one2many(
            'hr.employee.workhour.line', 
            'workhour_id', 'Detail'),
        }

class HrEmployee_festivity(osv.osv):
    ''' Festivity manage:
        manage static festivity (also with from-to period)
        manage dynamic list of festivity (ex. Easter monday)
    '''    
    _name = 'hr.employee.festivity'
    _description = 'HR festivity'
    
    # TODO: function for compute festivity
    # TODO: function for validate: 
    #       static date (max day for day-month)
    #       from to period evaluation (no interference)
    #       no double comment in dynamic date 
    #          (2 Easter monday for ex. in the same year)
    
    def is_festivity(self, cr, uid, date, context=None):
        ''' Test if datetime element date is in festifity rules
        '''
        # Static festivity (periodic):
        date_ids = self.search(cr, uid, [
            ('static', '=', True), 
            ('periodic', '=', True), 
            ('day', '=', date.day),
            ('month', '=', date.month),
            ('periodic_from', '>=', date.year),
            ('periodic_to', '<=', date.year),
            ]) 
        if date_ids:
            return True

        # Static festivity not periodic:
        date_ids = self.search(cr, uid, [
            ('static', '=', True), 
            ('periodic', '=', False), 
            ('day', '=', date.day),
            ('month', '=', date.month),
            ]) 
        if date_ids:
            return True

        # Dinamic festivity:
        date_ids = self.search(cr, uid, [
            ('static', '=', False), 
            ('dynamic_date', '=', date.strftime("%Y-%m-%d")),
            ])
        if date_ids:
            return True
        return False
    
    _columns = {
        'name': fields.char('Description', size=64),

        # static festivity:
        'static': fields.boolean('Static festivity', 
            help="It means that every year this festivity is the same day "
                "(ex. Christmas = 25 of dec.), if not it's dynamic "
                "(ex. Easter monday)"),
        'day': fields.integer('Static day'),
        'month': fields.integer('Static month'),

        # static but periodic:
        'periodic': fields.boolean('Periodic festivity', 
            help="Festivity is only for a from-to period "
                "(ex.: Patronal festivity but for a period because of changing city)"),
        'periodic_from': fields.integer('From year'),
        'periodic_to': fields.integer('To year'),
        
        # dinamic festivity (no periodic is allowed):
        'dynamic_date': fields.date('Dynamic Date'),
        }

    _defaults = {
        'periodic_from': lambda *a: datetime.now().strftime('%Y'),
        'periodic_to': lambda *a: datetime.now().strftime('%Y'),
        }

# TODO Use he.employee? create a related field?
class ResUsers(osv.osv):
    """ Extra field form manage workhour plan, note: use res.users for fast
    """    
    _inherit = 'res.users'

    _columns = {
        'workhour_plan_id':fields.many2one(
            'hr.employee.workhour', 'Workhour plan', 
            help="Working time for this employee like: "
                "full time, part time etc. (for manage hour and presence)"),
        }
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
