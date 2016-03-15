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
from openerp.tools.sql import drop_view_if_exists
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class MrpProductionStat(orm.Model):
    ''' Statistic data
    '''
    _name = 'mrp.production.stats'
    _description = 'MRP stats'
    _order = 'date'
    _rec_name = 'date'

    _columns = {
        'date': fields.date('Date', required=True),
        'total': fields.integer('Total', required=True), 
        'startup': fields.float('Start up time', digits=(16, 3)),     
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade'),
        }

    _defaults = {
        'date': lambda *x: datetime.now.strftime(DEFAULT_SERVER_DATE_FORMAT),    
        }

class MrpProductionStatMixed(osv.osv):
    ''' Create view object
    '''
    _name = 'mrp.production.stats.mixed'
    _description = 'MRP stats mixed'
    _auto = False
    
    _columns = {
        'name': fields.char('MRP name', required=True, readonly=True),
        'production_id': fields.many2one(
            'mrp.production', 'Production', readonly=True), 
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', readonly=True), 
        'qty': fields.float('Total q.', readonly=True),
        'lavoration_qty': fields.float('Lavoration q.', readonly=True),

    
        #'name': fields.char('Year', required=False, readonly=True),
        #'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
        #                          ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month', readonly=True),
        #'supply_units':fields.float('Supply Units', readonly=True),
        #'ref':fields.char('Source document', readonly=True),
        #'code': fields.char('Country code', size=2, readonly=True),
        #'intrastat_id': fields.many2one('report.intrastat.code', 'Intrastat code', readonly=True),
        #'weight': fields.float('Weight', readonly=True),
        #'value': fields.float('Value', readonly=True, digits_compute=dp.get_precision('Account')),
        #'type': fields.selection([('import', 'Import'), ('export', 'Export')], 'Type'),
        #'currency_id': fields.many2one('res.currency', "Currency", readonly=True),
        }
        
    def init(self, cr):
        drop_view_if_exists(cr, 'mrp_production_stats_mixed')
        cr.execute("""
            CREATE or REPLACE view mrp_production_stats_mixed as (
                SELECT 
                    wl.id as id,
                    wl.name as name,
                    wl.production_id as production_id,
                    wl.workcenter_id as workcenter_id,
                    wl.qty as qty,
                    wl.lavoration_qty as lavoration_qty
                FROM
                    mrp_production_workcenter_line wl    
                WHERE 
                    wl.state != 'cancel'
                )""")
        
        TODO_tmp = """
            create or replace view report_intrastat as (
                select
                    to_char(inv.create_date, 'YYYY') as name,
                    to_char(inv.create_date, 'MM') as month,
                    min(inv_line.id) as id,
                    intrastat.id as intrastat_id,
                    upper(inv_country.code) as code,
                    sum(case when inv_line.price_unit is not null
                            then inv_line.price_unit * inv_line.quantity
                            else 0
                        end) as value,
                    sum(
                        case when uom.category_id != puom.category_id then (pt.weight_net * inv_line.quantity)
                        else (pt.weight_net * inv_line.quantity * uom.factor) end
                    ) as weight,
                    sum(
                        case when uom.category_id != puom.category_id then inv_line.quantity
                        else (inv_line.quantity * uom.factor) end
                    ) as supply_units,

                    inv.currency_id as currency_id,
                    inv.number as ref,
                    case when inv.type in ('out_invoice','in_refund')
                        then 'export'
                        else 'import'
                        end as type
                from
                    account_invoice inv
                    left join account_invoice_line inv_line on inv_line.invoice_id=inv.id
                    left join (product_template pt
                        left join product_product pp on (pp.product_tmpl_id = pt.id))
                    on (inv_line.product_id = pp.id)
                    left join product_uom uom on uom.id=inv_line.uos_id
                    left join product_uom puom on puom.id = pt.uom_id
                    left join report_intrastat_code intrastat on pt.intrastat_id = intrastat.id
                    left join (res_partner inv_address
                        left join res_country inv_country on (inv_country.id = inv_address.country_id))
                    on (inv_address.id = inv.partner_id)
                where
                    inv.state in ('open','paid')
                    and inv_line.product_id is not null
                    and inv_country.intrastat=true
                group by to_char(inv.create_date, 'YYYY'), to_char(inv.create_date, 'MM'),intrastat.id,inv.type,pt.intrastat_id, inv_country.code,inv.number,  inv.currency_id
            )"""

class MrpProduction(orm.Model):
    ''' Statistic data
    '''
    _inherit = 'mrp.production'
    
    # Button events:
    def start_blocking_stats(self, cr, uid, ids, context=None):
        ''' Save current production to check difference
        '''
        blocked = sum([item.product_uom_maked_sync_qty for item in self.browse(
            cr, uid, ids, context=context)[0].order_line_ids])
        self.write(cr, uid, ids, {
            'stat_start_total': blocked,            
            }, context=context)
        return True
    
    def stop_blocking_stats(self, cr, uid, ids, context=None):
        ''' Save current production in log events
        '''
        blocked = sum([item.product_uom_maked_sync_qty for item in self.browse(
            cr, uid, ids, context=context)[0].order_line_ids])
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]    
        total = blocked - mrp_proxy.stat_start_total
        date = mrp_proxy.stat_start_date or datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT)
            
        # Create new stat record:
        self.pool.get('mrp.production.stats').create(cr, uid, {
            'date': date,
            'total': total,
            'startup': mrp_proxy.stat_startup,
            'mrp_id': ids[0],            
            }, context=context)
        return True    
    
    _columns = {
        'stat_start_date': fields.date('Ref. Date', 
            help='Ref. date for blocking operation'),
        'stat_start_total': fields.integer('Ref. Total',
            help='Total current item when start blocking operation'),
        'stat_startup': fields.float('Start up time', digits=(16, 3)),     
        'stats_ids': fields.one2many(
            'mrp.production.stats', 'mrp_id', 'Stats'), 
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
