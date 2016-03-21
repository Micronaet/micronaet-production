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
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', required=True), 
        'date': fields.date('Date', required=True),
        'total': fields.integer('Total', required=True), 
        'workers': fields.integer('Workers'),
        'hour': fields.float('Tot. H'),
        'startup': fields.float('Start up time', digits=(16, 3)),     
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade'),
        }

    _defaults = {
        'date': lambda *x: datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),    
        }

class MrpProductionStatMixed(osv.osv):
    ''' Create view object
    '''
    _name = 'mrp.production.stats.mixed'
    _description = 'MRP stats mixed'
    _order = 'date_planned desc'
    _rec_name = 'date_planned'
    _auto = False
    
    # Button event:
    def nothing(self, cr, uid, ids, context=None):
        ''' Dummy button
        '''
        return True

    _columns = {
        # mrp.production.workcenter.line:
        #'name': fields.char('MRP name', readonly=True),
        'is_today': fields.boolean('Is today', readonly=True),
        'date_planned': fields.date('Date planned', readonly=True),
        'product_id': fields.many2one(
            'product.product', 'Family', readonly=True), 
        'production_id': fields.many2one(
            'mrp.production', 'Production', readonly=True), 
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', readonly=True), 
        'lavoration_qty': fields.float('Lavoration q.', readonly=True),
        'hour': fields.float('Tot. H.', readonly=True),
        'workers': fields.integer('Workers', readonly=True),
        'startup': fields.float('Startup', readonly=True),
        
        # sale.order.line:
        'todo_qty': fields.float('Total q.', readonly=True),
        'maked_qty': fields.integer('Done q.', readonly=True),
        'remain_qty': fields.float('Remain q.', readonly=True),
        }
        
    def init(self, cr):
        drop_view_if_exists(cr, 'mrp_production_stats_mixed')
        cr.execute("""
            CREATE or REPLACE view mrp_production_stats_mixed as (
                SELECT 
                    min(st.id) as id,
                    st.date as date_planned,
                    sum(st.total) as maked_qty,
                    sum(st.startup) as startup,
                    sum(st.workers) as workers,
                    sum(st.hour) as hour,
                    st.workcenter_id as workcenter_id,
                    mrp.id as production_id,

                    mrp.product_id as product_id,

                    DATE(st.date) = DATE(now()) as is_today,

                    '' as name,
                    0 as todo_qty,
                    0 as remain_qty,
                    0 as lavoration_qty
                FROM 
                        mrp_production mrp
                    JOIN 
                        mrp_production_stats st
                    ON 
                        (st.mrp_id = mrp.id)
                GROUP BY
                    st.date,
                    st.workcenter_id,
                    mrp.product_id,
                    mrp.id
                )""") # HAVING mrp.state != 'cancel' mrp.workcenter_id


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
        ''' Get default and open wizard
        '''
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        blocked = sum([item.product_uom_maked_sync_qty for item in self.browse(
            cr, uid, ids, context=context)[0].order_line_ids])
        total = blocked - mrp_proxy.stat_start_total

        ctx = context.copy()
        try:
            workcenter_id = mrp_proxy.lavoration_ids[0].workcenter_id.id
        except:
            workcenter_id = False    
        try:
            workers = mrp_proxy.lavoration_ids[0].workers
        except:
            workers = 0
        try:
            hour = mrp_proxy.lavoration_ids[0].duration
        except:
            hour = 0
        
        ctx.update({
            #'default_workcenter_id': 
            'default_total': total,
            'default_mrp_id': mrp_proxy.id,
            'default_workcenter_id': workcenter_id,
            'default_workers': workers,
            'default_hour': hour,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Stats'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mrp.production.create.stats.wizard',
            'domain': [],
            'context': ctx,
            'target': 'new',
            'nodestroy': False,
        }
            
    
    _columns = {
        'stat_start_total': fields.integer('Ref. Total',
            help='Total current item when start blocking operation'),
        'stats_ids': fields.one2many(
            'mrp.production.stats', 'mrp_id', 'Stats'), 
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
