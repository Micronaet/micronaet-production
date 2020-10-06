#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import pdb
import logging
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class SaleOrderLine(orm.Model):
    """ Model name: Sale line
    """
    _inherit = 'sale.order.line'

    # Button:
    def bom_for_product_view_form(self, cr, uid, ids, context=None):
        """ Open product BOM:
        """
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            'mrp_online_label', 'bom_for_product_view_form')[1]

        line = self.browse(cr, uid, ids, context=context)[0]
        product_id = line.product_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM Exploded'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': product_id,
            'res_model': 'sale.order.line',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    # UTILITY:
    # -------------------------------------------------------------------------
    def get_bom_html(self, cr, uid, product_id, context=None):
        """ PHP call for get BOM
            context parameters:
                > 'noheader': hide header
                > 'show_ready': show only show ready category
                > 'expand': expand halfwork
                > 'qty': calculate total for qty producey
        """
        # Read parameters:
        if context is None:
            context = {}

        noheader = context.get('noheader', False)
        show_ready = context.get('show_ready', False)
        expand = context.get('expand', True)
        qty = context.get('qty', 1.0)

        bom = ''
        product_pool = self.pool.get('product.product')
        product_proxy = product_pool.browse(
            cr, uid, product_id, context=context)

        # ---------------------------------------------------------------------
        # BOM Lines:
        # ---------------------------------------------------------------------
        for item in sorted(product_proxy.dynamic_bom_line_ids,
                           key=lambda x: (
                               not x.product_id.half_bom_id,
                               x.product_id.default_code,
                               )):
            category = item.category_id
            product = item.product_id

            if show_ready and not category.show_ready:
                continue # jump category not in show ready status

            # if item.relative_type == 'half'\
            if product.bom_placeholder:
                tag_class = 'placeholder'
            elif product.half_bom_id:
                tag_class = 'halfworked'
            else:
                tag_class = 'component'

            bom += '''
                <tr class="%s">
                    <td colspan="2">%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s %s</td>
                </tr>
                ''' % (
                    tag_class,
                    product.default_code,
                    product.name,
                    item.category_id.name,
                    int(item.product_qty * qty),
                    item.product_uom.name.lower(),
                    )

            # Add sub elements (for halfworked)
            if expand:
                for cmpt in product.half_bom_id.bom_line_ids:
                    bom += '''
                    <tr class="material">
                        <td>>>></td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>&nbsp;</td>
                        <td>%s %s</td>
                    </tr>
                    ''' % (
                        cmpt.product_id.default_code,
                        cmpt.product_id.name,
                        cmpt.product_qty,
                        cmpt.product_uom.name.lower(),
                        )

        # ---------------------------------------------------------------------
        # Add header:
        # ---------------------------------------------------------------------
        if noheader:
            header_title = '''
                <tr>
                    <th colspan="9">Componenti da approntare:</th>
                </tr>
                '''
        else:
            header_title = '''
                <tr>
                    <th colspan="2">%s</th>
                    <th colspan="3">%s [%s]</th>
                </tr>
                ''' % (
                    self._php_button_bar,
                    product_proxy.default_code,
                    product_proxy.name,
                    )

        res = _('''
            <tr colspan="9">
            <table class="bom">
                %s
                <tr>
                    <th colspan="2">Codice</th>
                    <th>Descrizione</th>
                    <th>Categoria</th>
                    <th>Q.</th>
                </tr>
                %s
            </table>            
            </tr>
            ''') % (
                header_title,
                bom,
                )
        return res

    # TODO move in note system (taken from old mrp_direct_line):
    def get_notesystem_for_line(self, cr, uid, ids, context=None):
        """ Note system for line
        """
        def add_domain_note(self, cr, uid, line, block='pr', context=None):
            """ Add domain note after search
            """
            label_image = '''
                <img src="/images/label.jpg" 
                alt="Etichetta personalizzata" 
                style="width:16px;height:16px;"
                title="Etichetta personalizzata"/> 
                '''

            # Pool used:
            product_pool = self.pool.get('product.product')
            note_pool = self.pool.get('note.note')

            domain = product_pool.get_domain_note_event_filter(
                cr, uid, line, block=block, context=context)
            if domain == False:  # no domain
                return ''
            note_ids = note_pool.search(
                cr, uid, domain, context=context)

            note_text = ''
            for note in note_pool.browse(
                    cr, uid, note_ids, context=context):
                note_text += \
                    '<div class="p_note %s">%s<b>%s</b> %s</div>' % (
                        '"fg_red"' if note.print_label else '',
                        label_image if note.print_label else '',
                        note.name or '',
                        note.description or '',
                    )
            return note_text

        line = self.browse(cr, uid, ids, context=context)[0]
        note_text = ''
        # TODO add only category for production in filter!

        # Product note:
        mask = '<b class="category_note">NOTE %s: </b><br/>%s'
        res = add_domain_note(
            self, cr, uid, line, block='pr', context=context)
        if res:
            note_text += mask % ('PRODOTTO', res)
        # Partner note:
        res = add_domain_note(
            self, cr, uid, line, block='pa', context=context)
        if res:
            note_text += mask % ('PARTNER', res)
        # Address note:
        res = add_domain_note(
            self, cr, uid, line, block='ad', context=context)
        if res:
            note_text += mask % ('INDIRIZZO', res)
        # Order note:
        res = add_domain_note(
            self, cr, uid, line, block='or', context=context)
        if res:
            note_text += mask % ('ORDINE', res)
        # Detail note:
        res = add_domain_note(
            self, cr, uid, line, block='pr-de', context=context)
        if res:
            note_text += mask % ('DETTAGLIO', res)

        # Partner product note:
        res = add_domain_note(
            self, cr, uid, line, block='pr-pa', context=context)
        if res:
            note_text += mask % ('PRODOTTO-CLIENTE', res)
        # Address product note:
        res = add_domain_note(
            self, cr, uid, line, block='pr-ad', context=context)
        if res:
            note_text += mask % ('PRODOTTO-INDIRIZZO', res)
        # Address product order note:
        res = add_domain_note(
            self, cr, uid, line, block='pr-or', context=context)
        if res:
            note_text += mask % ('PRODOTTO-ORDINE', res)
        return note_text

    def stop_block_start_label(self, cr, uid, ids, context=None):
        """ Close stats block button event
        """
        mrp_pool = self.pool.get('mrp.production')
        line = self.browse(cr, uid, ids, context=context)
        return mrp_pool.stop_blocking_stats(
            cr, uid, [line.mrp_id.id], context=context)

    def close_production_online(self, cr, uid, ids, context=None):
        """ Close and go next
        """
        # Close remain to produce:
        self.close_production(cr, uid, ids, context=context)

        # Go next:
        return self.button_next_line(cr, uid, ids, context=context)

    def button_next_line(self, cr, uid, ids, context=None):
        """ Call next from sale line
        """
        mrp_pool = self.pool.get('mrp.production')
        line = self.browse(cr, uid, ids, context=context)
        return mrp_pool.button_next_line(
            cr, uid, [line.mrp_id.id], context=context)

    # Fields function:
    def _get_future_line(self, cr, uid, ids, field_names, arg=None,
                         context=None):
        """ Next lines
            > ensure one!
        """
        # Parameter:
        preview_total = 3  # TODO put in params?
        res = {}

        # Context setup:
        context_next = context.copy()
        context_next['extra_line_item'] = preview_total

        # Launch from MRP finding in line:
        mrp_pool = self.pool.get('mrp.production')
        line = self.browse(cr, uid, ids, context=context)
        res[ids[0]] = mrp_pool.get_first_line_undone(
            cr, uid, [line.mrp_id.id], context=context_next)
        return res

    def _get_mrp_stats_online(self, cr, uid, ids, field_names, arg=None,
                              context=None):
        """ MRP statistic ensure one
        """
        res = {}
        line = self.browse(cr, uid, ids, context=context)[0]
        mrp = line.mrp_id

        # This because fields dont' work:
        mrp_pool = self.pool.get('mrp.production')
        record = mrp_pool._get_total_line(
            cr, uid, [mrp.id], False, False, context=context)[mrp.id]
        res[ids[0]] = _('[MRP %s] Totale: %s - Fatti: %s - Residui: %s') % (
            mrp.name,
            record['total_line_todo'],
            record['total_line_done'],
            record['total_line_remain'],
        )
        return res

    def _get_note_system_online(
            self, cr, uid, ids, field_names, arg=None, context=None):
        """ MRP statistic ensure one
        """
        res = {}
        res[ids[0]] = self.get_notesystem_for_line(
            cr, uid, ids, context=context)
        return res

    def _get_bom_exploded_online(
            self, cr, uid, ids, field_names, arg=None, context=None):
        """ MRP statistic ensure one
        """
        res = {}
        line = self.browse(cr, uid, ids, context=context)[0]
        product_id = line.product_id.id
        res[ids[0]] = self.get_bom_html(
            cr, uid, product_id, context=context)
        return res

    _columns = {
        'future_line_ids': fields.function(
            _get_future_line, method=True, readonly=True,
            type='one2many',
            relation='sale.order.line',
            string='Future line'),
        'production_status_online': fields.function(
            _get_mrp_stats_online, method=True, readonly=True,
            type='char', size=100, string='Production status'),
        'note_system_online': fields.function(
            _get_note_system_online, method=True, readonly=True,
            type='text', string='Note system'),
        'bom_exploded_online': fields.function(
            _get_bom_exploded_online, method=True, readonly=True,
            type='text', string='BOM',
        )

    }


class ResUsers(orm.Model):
    """ Model name: Res Users
    """
    _inherit = 'res.users'

    _columns = {
        'label_workcenter_id': fields.many2one(
            'mrp.workcenter', 'Default Line',
        )
    }


class MrpProduction(orm.Model):
    """ Model name: MRP Production
    """
    _inherit = 'mrp.production'

    def get_first_line_undone(self, cr, uid, ids, context=None):
        """ Return first undone line to be produced,
            context: extra_line_item = extra line ID returned
        """
        if context is None:
            context = {}

        # Extra line management (for next line preview)
        extra_line_item = context.get('extra_line_item')
        if extra_line_item < 0:
            extra_line_item = 0

        # Extract not complete line (and extra line):
        mrp = self.browse(cr, uid, ids, context=context)[0]
        this_line_id = False
        sorted_line = sorted(mrp.order_line_ids, key=lambda x: x.mrp_sequence)
        i = 0
        for line in sorted_line:
            if line.product_uom_maked_sync_qty >= (
                    line.product_uom_qty + line.mx_assigned_qty):
                continue  # All done

            # A. Default run:
            this_line_id = line.id
            i += 1

            # B. Extra line run mode:
            if extra_line_item:
                next_line_ids = []
                while extra_line_item:
                    try:
                        future = sorted_line[i]
                        i += 1
                    except:
                        break  # List finished!
                    if not future:
                        break
                    if future.id == this_line_id:
                        continue
                    if future.product_uom_maked_sync_qty >= (
                            future.product_uom_qty + future.mx_assigned_qty):
                        continue  # All done

                    next_line_ids.append(future.id)
                    extra_line_item -= 1  # Back counter
                return next_line_ids
            break

        # A. Default run
        if not this_line_id:
            raise osv.except_osv(
                _('Error'),
                _('End of production, please close and confirm statistic!'),
                )
        return this_line_id

    def button_next_line(self, cr, uid, ids, context=None):
        """ Next line operation
        """
        model_pool = self.pool.get('ir.model.data')
        line_id = self.get_first_line_undone(
            cr, uid, ids, context=context)

        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'sale_order_label_online_view_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Production Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': line_id,
            'res_model': 'sale.order.line',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def start_block_start_label(self, cr, uid, ids, context=None):
        """ Launch stats start action and open view for production start
        """
        mrp = self.browse(cr, uid, ids, context=context)[0]
        if not mrp.stat_start_datetime:  # Yet started, datetime present!
            self.start_blocking_stats(cr, uid, ids, context=context)
        return self.button_next_line(cr, uid, ids, context=context)

    def my_production_for_label_server_action(
            self, cr, uid, ids, context=None):
        """ My production list
        """
        model_pool = self.pool.get('ir.model.data')
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'online_label_mrp_view_tree')[1]

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        label_workcenter_id = user.label_workcenter_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id': ,
            'res_model': 'mrp.production',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree')],
            'domain': [
                ('label_workcenter_id', '=', label_workcenter_id),
                ('state', 'not in', ('cancel', 'done'))
            ],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def open_production_detail(self, cr, uid, ids, context=None):
        """ Open form
        """
        # model_pool = self.pool.get('ir.model.data')
        # view_id = model_pool.get_object_reference(
        #     'module_name', 'view_name')[1]
        view_id = False
        item_id = ids[0]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': item_id,
            'res_model': 'mrp.production',
            'view_id': view_id,
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'label_workcenter_id': fields.many2one(
            'mrp.workcenter', 'Linea di lavorazione',
        )
    }

