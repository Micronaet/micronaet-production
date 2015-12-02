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

class HrWorkhour(orm.Model):
    ''' Manage workhour plan as employee contract
    '''    
    _name = 'hr.workhour'
    _description = 'Workhour plan'
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'note': fields.text('Note'),
        }

class HrWorkhourDay(orm.Model):
    ''' Class for manage Work hour for each day of the week
    '''
    
    _name = 'hr.workhour.day'
    _description = 'Employee work hour'
    _rec_name = 'weekday'

    # weekday python value:
    get_weekday = [ 
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
        ]
            
    _columns = {
        'workhour_id': fields.many2one('hr.workhour', 'Workhour'),
        'weekday': fields.selection(
            get_weekday, 'Weekday', select=True, readonly=False),
        'hour': fields.integer('Label')            
        }
        
    _defaults = {
        'hour': lambda *x: 8,
        }    

class HrWorkhour(orm.Model):
    ''' Class for manage Work hour
    '''

    _inherit = 'hr.workhour'
    
    _columns = {
        'day_ids': fields.one2many('hr.workhour.day', 'workhour_id', 'Day'),
        }

class HrWorkhourFestivity(osv.osv):
    ''' Festivity manage:
        manage static festivity (also with from-to period)
        manage dynamic list of festivity (ex. Easter monday)
    '''    
    _name = 'hr.workhour.festivity'
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
            ('dynamic_from_date', '>=', date.strftime('%Y-%m-%d')),
            ('dynamic_to_date', '<=', date.strftime('%Y-%m-%d')),
            ])
        if date_ids:
            return True
        return False
    
    _columns = {
        'name': fields.char('Description', size=64),

        # static festivity:
        'static': fields.boolean('Static festivity', 
            help='It means that every year this festivity is the same day '
                '(ex. Christmas = 25 of dec.), if not it's dynamic '
                '(ex. Easter monday)'),
        'day': fields.integer('Static day'),
        'month': fields.integer('Static month'),

        # static but periodic:
        'periodic': fields.boolean('Periodic festivity', 
            help='Festivity is only for a from-to period '
                '(ex.: Patronal festivity but for a period because of '
                'changing city)'),
        'periodic_from': fields.integer('From year >='),
        'periodic_to': fields.integer('To year <='),
        
        # dinamic festivity (no periodic is allowed):
        'dynamic_from_date': fields.date('From date >='),
        'dynamic_to_date': fields.date('To date <='),
        }

    _defaults = {
        'periodic_from': lambda *a: datetime.now().strftime('%Y'),
        'periodic_to': lambda *a: datetime.now().strftime('%Y'),
        }

# TODO Use he.employee? create a related field?
class ResUsers(osv.osv):
    ''' Extra field form manage workhour plan, note: use res.users for fast
    '''    
    _inherit = 'res.users'

    _columns = {
        'workhour_plan_id':fields.many2one(
            'hr.workhour', 'Workhour plan', 
            help='Working time for this employee like: '
                'full time, part time etc. (for manage hour and presence)'),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
