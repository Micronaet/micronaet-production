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

class bom_lavoration_phase(orm.Model):
    ''' Phase for lavoration
    '''
    _name = 'mrp.bom.lavoration.phase'
    _description = 'BOM Lavoration phase'
    
    _columns = {
        'name': fields.char('Phase', size=64, required=True),
        'line_id': fields.many2one('mrp.workcenter', 
            'Default line', required=True, ondelete='set null'),            
        'unload_material': fields.boolean('Unload material', 
            help='This phase unload material from stock'),
        'note': fields.text('Note'),
        # TODO must be unique in table:
        'production_phase': fields.boolean('Production phase'),
    }
    
    _defaults = {
        'unload_material': lambda *x: False,
        'production_phase': lambda *x: False,
        }

class bom_lavoration(orm.Model):
    ''' Lavoration for BOM
    '''
    _name = 'mrp.bom.lavoration'
    _description = 'BOM Lavoration'
    _order = 'create_date,level'
    _rec_name = 'level'
    
    def name_get(self, cr, uid, ids, context=None):
        """
        Return a list of tuples contains id, name.
        result format : {[(id, name), (id, name), ...]}
        
        @param cr: cursor to database
        @param uid: id of current user
        @param ids: list of ids for which name should be read
        @param context: context arguments, like lang, time zone
        
        @return: returns a list of tupples contains id, name
        """ 
        res = []
        for item in self.browse(cr, uid, ids, context=context):
            try: 
                res.append((item.id, item.phase_id.name))
            except:
                res.append((item.id, _("No phase")))
            
        return res
    
    
    _columns = {        
        'level': fields.integer('Level'),
        'phase_id': fields.many2one('mrp.bom.lavoration.phase', 'Phase', 
            required=True, ondelete='set null'),
        'fixed': fields.boolean('Fixed', required=False),
        'quantity': fields.float('Quantity', digits=(10, 2), 
            help="Number of piece producted in duration time"),
        'duration': fields.float('BOM Duration', digits=(10, 2),
            help="Duration in hour:minute for lavoration of quantity piece"),
        #'uom_id': fields.many2one('product.uom', 'U.M.', 
        #    ondelete='set null'),
        'workers': fields.integer('Default workers'),
        'line_id': fields.many2one('mrp.workcenter', 'Line', 
            required=True, ondelete='set null'),            
        'bom_id': fields.many2one('mrp.bom', 'BOM', 
            ondelete='cascade'),

        # Show database fields:
        'create_date': fields.datetime('Create date', readonly=True),
        }
        
    _defaults = {
        'level': lambda *x: 1,
        'workers': lambda *x: 1,        
        'duration': lambda *x: 1.0,
        'quantity': lambda *x: 1,
        }
        
class mrp_bom(orm.Model):
    ''' Add relation fields
    '''
    _inherit = 'mrp.bom'
    
    _columns = {
        'has_lavoration': fields.boolean('Has lavoration'),
        'lavoration_ids': fields.one2many('mrp.bom.lavoration', 'bom_id', 
            'Lavoration'),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
