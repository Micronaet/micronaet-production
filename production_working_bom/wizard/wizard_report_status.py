# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv import osv, fields


# WIZARD PRINT REPORT ########################################################
class mrp_production_status_wizard(osv.osv_memory):
    ''' Parameter for product status per day
    '''    
    
    _name = 'mrp.production.status.wizard'
    _description = 'Product status wizard'
    
    # Button events:
    def print_report(self, cr, uid, ids, context=None):
        ''' Redirect to bom report passing parameters
        ''' 
        wiz_proxy = self.browse(cr, uid, ids)[0]

        datas = {}
        if wiz_proxy.days:
            datas['days'] = wiz_proxy.days

        datas['active'] = wiz_proxy.active
        datas['negative'] = wiz_proxy.negative
        datas['with_medium'] = wiz_proxy.with_medium
        datas['month_window'] = wiz_proxy.month_window

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'webkitworkstatus',
            'datas': datas,
        }
        
    _columns = {
        'days':fields.integer('Days from today', required=True),
        'active':fields.boolean('Only record with data', required=False, 
            help="Show only product and material with movement"),
        'negative': fields.boolean('Only negative', required=False, 
            help="Show only product and material with negative value in range"),
        'month_window':fields.integer('Statistic production window ', 
            required=True, help="Month back for medium production monthly index (Kg / month of prime material)"),
        'with_medium': fields.boolean('With m(x)', required=False, 
            help="if check in report there's production m(x), if not check report is more fast"),        
        }
        
    _defaults = {
        'days': lambda *a: 7,
        'active': lambda *a: False,
        'negative': lambda *a: False,
        'month_window': lambda *x: 2,
        'with_medium': lambda *x: True,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
