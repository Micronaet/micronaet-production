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

class ProductProductWoodText(orm.Model):
    """ Model name: Product Product FSC Text
    """
    
    _name = 'product.product.wood.text'
    _description = 'Wood text'
    _order = 'mode,name'
    
    _columns = {        
        'name': fields.char('Name', size=80, required=True),
        'mode': fields.selection([
            ('material', 'Material'),
            ('group', 'Group'),
            ], 'Mode', required=True),
        }

    _defaults = {
        'mode': lambda *x: 'material',
        }    

class ProductProductWood(orm.Model):
    """ Model name: ProductProductFSC
    """
    
    _name = 'product.product.wood'
    _description = 'Wood certification description for product'
    _order = 'mode,sequence,name'
    
    _columns = {        
        'sequence': fields.integer('Sequence', required=True),
        'name': fields.char('Name', size=64, required=True),
        'text': fields.char('Text', size=100, required=True, translate=True),
        'company_id': fields.many2one('res.company', 'Company'),
        'start_code': fields.text('Start code',
            help='Start code of product certification, ex.:127|128|129'),    
        'fixed_code': fields.text('Fixed code',
            help='List of fixed code, ex.:127TXANBIBE|128TXANBIBE'),    
        'mode': fields.selection([
            ('fsc', 'FSC'),
            ('pefc', 'PEFC'),
            ], 'Mode', required=True),
        }

    _defaults = {
        'mode': lambda *x: 'pefc',
        }    

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    
    _inherit = 'res.company'
    
    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    # Utility:
    def force_fsc_pefc_setup_code(self, cr, uid, ids, mode, context=None):
        ''' Utility for setup all 2 check box
        '''
        _logger.info('Start update procedure')
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        wood_pool = self.pool.get('product.product.wood')
        
        # ---------------------------------------------------------------------
        # Remove all check for this mode type:
        # ---------------------------------------------------------------------
        query = '''
            UPDATE product_product 
            SET %s_certified_id=null;
            ''' % mode
        cr.execute(query)
        _logger.info('Clean previous selection: \n%s' % query)

        wood_ids = wood_pool.search(cr, uid, [
            ('mode', '=', mode),
            ], context=context)
        for wood in wood_pool.browse(cr, uid, wood_ids, context=context):
            _logger.info('[%s] Updating %s product...' % (
                wood.sequence, wood.name))

            # -----------------------------------------------------------------
            # Start code part:            
            # -----------------------------------------------------------------
            start_code = wood.start_code or ''
            for start in start_code.split('|'):
                # Search product start with this:
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=ilike', '%s%%' % start),
                    ], context=context)
                product_pool.write(cr, uid, product_ids, {
                    '%s_certified_id' % mode: wood.id,
                    }, context=context)    
                _logger.info('Update %s product start with: %s' % (
                    len(product_ids),
                    start,
                    ))        

            # -----------------------------------------------------------------
            # Fixed code part:            
            # -----------------------------------------------------------------
            fixed_code = wood.fixed_code or ''
            for default_code in fixed_code.split('|'):
                default_code = default_code.strip()
                
                # Search product start with this:
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code),
                    ], context=context)
                product_pool.write(cr, uid, product_ids, {
                    '%s_certified_id' % mode: wood.id,
                    }, context=context)    
                _logger.info('Update %s product start with: %s' % (
                    len(product_ids),
                    start,
                    ))        

        _logger.info('End update procedure')
        return True
    
    def force_fsc_setup_code(self, cr, uid, ids, context=None):
        ''' Force FSC setup on code passed
        '''
        _logger.info('Force FSC')
        return self.force_fsc_pefc_setup_code(
            cr, uid, ids, 'fsc', context=context)

    def force_pefc_setup_code(self, cr, uid, ids, context=None):
        ''' Force PEFC setup on code passed
        '''
        _logger.info('Force PEFC')
        return self.force_fsc_pefc_setup_code(
            cr, uid, ids, 'pefc', context=context)

    # -------------------------------------------------------------------------        
    # Scheduled operations:        
    # -------------------------------------------------------------------------        
    def scheduled_force_fsc_pefc_text(self, cr, uid, context=None):
        ''' Call 2 botton event
        '''
        # Call button FSC:
        self.force_fsc_setup_code(cr, uid, False, context=context)
        # Call button PEFC:
        self.force_pefc_setup_code(cr, uid, False, context=context)
        return True
        
    def check_certification_from_product_line(
            self, cr, mode, line, date, company, context=None):
        ''' Check certification present for product in line passed
            Evaluation for print:
            1. there's one product with *_certified in the item list
            2. the document date must be > from certified date in company            
        '''        
        # TODO (used)??????
        mode = mode.lower()
        if mode not in ('fsc', 'pefc'):
            _logger.error('Mode must be: fsc or pefc!')
            return False # No show!
        
        field = '%s_certified' % mode    
        #if date
        return True
    
    _columns = {
        'fsc_certified': fields.boolean('FSC Certified'),
        'fsc_code': fields.char('FSC Code', size=50),
        'fsc_from_date': fields.date('FSC from date'),
        'fsc_logo': fields.binary(
            'FSC Logo', help='FSC document logo bottom part'),

        'pefc_certified': fields.boolean('PEFC Certified'),
        'pefc_code': fields.char('PEFC Code', size=50),
        'pefc_from_date': fields.date('PEFC from date'),
        'pefc_logo': fields.binary(
            'PEFC Logo', help='PEFC document logo bottom part'),
            
        'xfc_text_ids': fields.one2many(
            'product.product.wood', 'company_id', 'PEFC product text'),
        'xfc_document_note': fields.text('FSC, PEFC Document note',
            translate=True),
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'fsc_certified_id': fields.many2one(
            'product.product.wood', 'FSC text'),
        'pefc_certified_id': fields.many2one(
            'product.product.wood', 'PEFC text'),
            
        # Description for registry:
        'wood_material_text_id': fields.many2one(
            'product.product.wood.text', 'Materiale (registro)'),
        'wood_group_text_id': fields.many2one(
            'product.product.wood.text', 'Gruppo (registro)'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
