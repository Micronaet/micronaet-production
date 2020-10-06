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
    def open_product_schema(self, cr, uid, ids, context=None):
        """ Open product schema:
        """
        # TODO
        """
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'bom_for_product_view_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM Exploded'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'sale.order.line',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }"""
        return True

    def open_product_bom_html(self, cr, uid, ids, context=None):
        """ Open product BOM:
        """
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'bom_for_product_view_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM Exploded'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
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
    def get_bom_html(self, cr, uid, ids, context=None):
        """ HTML Field call
        """
        # Read parameters:
        if context is None:
            context = {}

        show_ready = False
        expand = True
        qty = 1.0

        bom = ''
        line = self.browse(cr, uid, ids, context=context)[0]
        product_proxy = line.product_id

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
                continue  # jump category not in show ready status

            # if item.relative_type == 'half'\
            tag_table = 'border: 0px solid black; width: 950px;' \
                        'font-size: 11px; margin: 5px; border-spacing: 0px;' \
                        'text-align: left;'

            if product.bom_placeholder:
                tag_style = 'font-size: 12px; background-color: #ffcccc;' \
                            'text-align: left;'
            elif product.half_bom_id:
                tag_style = 'font-size: 12px; background-color: #0099e6;' \
                            'text-align: left;'
            else:
                tag_style = 'font-size: 12px; background-color: #ffffcc;' \
                            'text-align: left;'
            tag_material = 'font-size: 12px; background-color: #cceeff;' \
                           'text-align: left;'

            bom += '''
                <tr style="%s">
                    <td colspan="2">%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s %s</td>
                </tr>
                ''' % (
                    tag_style,
                    product.default_code,
                    product.name,
                    item.category_id.name,
                    int(item.product_qty * qty),
                    item.product_uom.name.lower(),
                    )

            # Add sub elements (for semi worked)
            if expand:
                for cmpt in product.half_bom_id.bom_line_ids:
                    bom += '''
                    <tr style="%s">
                        <td>&nbsp;&nbsp;&nbsp;&nbsp;</td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>&nbsp;</td>
                        <td>%s %s</td>
                    </tr>
                    ''' % (
                        tag_material,
                        cmpt.product_id.default_code,
                        cmpt.product_id.name,
                        cmpt.product_qty,
                        cmpt.product_uom.name.lower(),
                        )

        # ---------------------------------------------------------------------
        # Add header:
        # ---------------------------------------------------------------------
        res = _('''
            <div><table style="%s">
                <tr>
                    <th colspan="2">Codice</th>
                    <th>Descrizione</th>
                    <th>Categoria</th>
                    <th>Q.</th>
                </tr>
                %s
            </table></div>            
            ''') % (
                tag_table,
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
            # TODO show when custom label!
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
                    '<div style="%s">%s<b>%s</b> %s</div>' % (
                        'color: red' if note.print_label else '',
                        label_image if note.print_label else '',
                        note.name or '',
                        note.description or '',
                    )
            return note_text

        line = self.browse(cr, uid, ids, context=context)[0]
        note_text = ''
        # TODO add only category for production in filter!

        # Product note:
        mask = '<b style="color: red">NOTE %s: </b><br/>%s'
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
        res[ids[0]] = self.get_bom_html(
            cr, uid, ids, context=context)
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
            _logger.warning(
                _('End of production, please close and confirm statistic!'))
        return this_line_id

    def button_next_line(self, cr, uid, ids, context=None):
        """ Next line operation
        """
        model_pool = self.pool.get('ir.model.data')
        line_id = self.get_first_line_undone(
            cr, uid, ids, context=context)
        if not line_id:
            return True
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

