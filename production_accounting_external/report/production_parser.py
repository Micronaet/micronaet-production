# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import pdb
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.report import report_sxw
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_date': self.get_date,

            # production report:
            'get_hour': self.get_hour,

            'get_report_extra_data': self.get_report_extra_data,
            'get_object_with_total': self.get_object_with_total,
            'get_object_with_total_cut': self.get_object_with_total_cut,
            'setup_data_mrp': self.setup_data_mrp,
            'setup_data_cut': self.setup_data_cut,
            'get_pre_production': self.get_pre_production,
            'get_frames': self.get_frames,
            'get_table': self.get_table,
            'get_materials': self.get_materials,
            'clean_note': self.clean_note,
            'get_product_components': self.get_product_components,
            # remain report:
            'get_object_remain': self.get_object_remain,
            'previous_record': self.previous_record,
            'clean_order': self.clean_order,

            # Note system:
            'get_note_system': self.get_note_system,
            'get_note_reference': self.get_note_reference,
        })

    def get_product_components(self, line, remain):
        """ Product component return data
            mode: key, value
        """
        product = line.product_id
        res = []
        components = self.product_components.get(product, {})
        for component in components:
            record = [component, []]
            for fabric in components[component]:
                record[1].append((
                    fabric, components[component][fabric] * remain,
                ))
            res.append(record)
        return res

    def clean_note(self, note):
        """ Remove if present ex production
            Bloc: "Ex.: MO02610"
        """
        if not note:
            return ''
        remove = 'Ex.: MO'
        code_len = 5

        if remove in note:
            note_list = note.split('Ex.: MO')
            res = '%s%s' % (
                note_list[0],
                note_list[-1][code_len:]  # remove code
                )
            return res.strip()

    def get_note_reference(self, note):
        """ Linked obj for note
        """
        def get_product(product):
            return product.default_code or product.name or ''

        # ---------------------------------------------------------------------
        # Line:
        # ---------------------------------------------------------------------
        if note.line_id:
            return 'Riga: %s ordine: %s' % (
                get_product(note.line_id.product_id),
                note.order_id.name,
                )

        # ---------------------------------------------------------------------
        # Order:
        # ---------------------------------------------------------------------
        elif note.product_id and note.order_id:
            return 'Ordine-Prodotto: %s-%s' % (
                note.order_id.name,
                get_product(note.product_id),
                )
        elif note.order_id:
            return 'Ordine: %s' % (
                note.order_id.name,
                )

        # ---------------------------------------------------------------------
        # Product:
        # ---------------------------------------------------------------------
        elif note.product_id and note.address_id:  # TODO order_id False
            return 'Destinazione-Prodotto: %s-%s' % (
                note.address_id.name,
                get_product(note.product_id),
                )
        elif note.product_id and note.partner_id:
            return 'Cliente-Prodotto: %s-%s' % (
                note.partner_id.name,
                get_product(note.product_id),
                )
        elif note.product_id:
            return 'Prodotto: %s' % (
                get_product(note.product_id),
                )

        # ---------------------------------------------------------------------
        # Partner and Address:
        # ---------------------------------------------------------------------
        elif note.address_id:
            return 'Destinazione: %s' % (
                note.address_id.name,
                )
        elif note.partner_id:
            return 'Cliente: %s' % (
                note.partner_id.name,
                )
        else:
            return 'Non chiaro il collegamento!'

    def get_note_system(self, department):
        """ Read all partner, destination, order, product, line from
            object and get all data from note system
            filter also depend on data
            department is the name of Production or Cut Department

            @return list
        """
        cr = self.cr
        uid = self.uid
        context = {}

        # Pool used:
        dept_pool = self.pool.get('note.department')
        type_pool = self.pool.get('note.type')
        note_pool = self.pool.get('note.note')

        # ---------------------------------------------------------------------
        # Find all type for filter note:
        # ---------------------------------------------------------------------
        # Get department ID:
        dept_ids = dept_pool.search(cr, uid, [
            ('name', '=', department),
            ], context=context)
        if not dept_ids:
            _logger.error('Nessun dipartimento %s presente' % department)
            return []
        dept_id = dept_ids[0]

        # Get type ID:
        type_ids = type_pool.search(cr, uid, [], context=context)
        selected_type_ids = []
        for item in type_pool.browse(
                cr, uid, type_ids, context=context):
            if dept_id in [c.id for c in item.department_ids]:
                selected_type_ids.append(item.id)
        if not selected_type_ids:
            _logger.error('Nessuna categoria con dipartimento %s' % department)
            return []

        # ---------------------------------------------------------------------
        # Find all note:
        # ---------------------------------------------------------------------
        # Generate control list for get note:
        partner_ids = []
        address_ids = []
        product_ids = []
        order_ids = []
        line_ids = []
        product_partic = []

        for sol in self.mrp_sol:  # order line (collected data during print)
            # Get check fields:
            partner_id = sol.order_id.partner_id.id
            address_id = sol.order_id.destination_partner_id.id
            product_id = sol.product_id.id
            order_id = sol.order_id.id
            line_id = sol.id

            # Update list:
            if partner_id and partner_id not in partner_ids:
                partner_ids.append(partner_id)
            if address_id and address_id not in address_ids:
                address_ids.append(address_id)
            if product_id and product_id not in product_ids:
                product_ids.append(product_id)
            if order_id and order_id not in order_ids:
                order_ids.append(order_id)
            if line_id and line_id not in line_ids:
                line_ids.append(line_id)

            # Partic:
            if partner_id and product_id:
                product_partic.append((partner_id, product_id))
            if address_id and product_id:
                product_partic.append((address_id, product_id))

        note_ids = note_pool.search(cr, uid, [
            ('type_id', 'in', selected_type_ids),  # only category
            ], context=context)
        note_selected = []

        for note in note_pool.browse(cr, uid, note_ids, context=context):
            partner_id = note.partner_id.id
            address_id = note.address_id.id
            product_id = note.product_id.id
            order_id = note.order_id.id
            line_id = note.line_id.id

            if line_id in line_ids:  # or order_id in order_ids:
                note_selected.append(note)
            elif not line_id and order_id in order_ids:
                note_selected.append(note)
            elif (partner_id, product_id) in product_partic:
                note_selected.append(note)
            elif (address_id, product_id) in product_partic:
                note_selected.append(note)
            # elif address_id in address_ids and product_id in product_ids:
            #    # Address - Product
            #    note_selected.append(note)
            # elif partner_id in partner_ids and product_id in product_ids:
            #    # Partner - Product
            #    note_selected.append(note)

            elif not address_id and not partner_id and \
                    product_id in product_ids:
                # Product
                note_selected.append(note)

            # Only partner / address (no product partic and no order partic)
            elif address_id in address_ids and not product_id and not order_id:
                note_selected.append(note)
            elif partner_id in partner_ids and not product_id and not order_id\
                    and not address_id:  # only partner no order product addr.
                note_selected.append(note)

        return sorted(note_selected, key=lambda x: (
            x.print_label,  # after label
            x.type_id.name,  # Change order type (after label)
            x.partner_id.name or '',
            x.address_id.name or '',
            x.product_id.default_code or '',
            x.order_id.name or '',
            ))

    def get_pre_production(self):
        """ List of family with order to do and order planned (open)
        """
        res = {}
        mrp_pool = self.pool.get('mrp.production')
        sol_pool = self.pool.get('sale.order.line')

        # ---------------------------------------------------------------------
        # Read open productions:
        # ---------------------------------------------------------------------
        mrp_family = {}
        mrp_ids = mrp_pool.search(self.cr, self.uid, [
            ('state', 'not in', ('cancel', 'done'))])

        for mrp in mrp_pool.browse(self.cr, self.uid, mrp_ids):
            family_id = mrp.product_id.id
            # bom_id.product_tmpl_id
            if family_id not in mrp_family:
                mrp_family[family_id] = [0.0, 0.0]  # OC, Done

            for line in mrp.order_line_ids:
                mrp_family[family_id][0] += line.product_uom_qty
                mrp_family[family_id][1] += line.product_uom_maked_sync_qty

        # ---------------------------------------------------------------------
        # Open line not linked:
        # ---------------------------------------------------------------------
        sol_ids = sol_pool.search(self.cr, self.uid, [
            ('mrp_id', '=', False),
            ('pricelist_order', '=', False),
            ('go_in_production', '=', True),
            ('is_manufactured', '=', True),
            ('mx_closed', '=', False),
            ])

        for line in sol_pool.browse(self.cr, self.uid, sol_ids):
            family = line.product_id.family_id
            if family in res:
                res[family][1] += line.product_uom_qty
                res[family][2] += line.product_uom_maked_sync_qty
            else:
                res[family] = [
                    family.name,
                    line.product_uom_qty,
                    line.product_uom_maked_sync_qty,
                    line.mrp_similar_info,
                    line.mrp_similar_total,
                    mrp_family.get(family.id, [0.0, 0.0]),
                    ]
        r = [res[k] for k in res]
        return sorted(r)

    def clean_order(self, name):
        """ Clean order:
        """
        try:
            if name.startswith('MX'):
                return name.split('-')[-1].split('/')[0]
            else:
                return name.split('/')[-1]
        except:
            return name

    def previous_record(self, value=False):
        """ Save passed value as previous record
            value: 'init' for setup first False record
                   data for set up this record
                   Nothing for get element
        """
        if value == 'init':
            self.previous_record_value = False
            return ''
        if value:  # set operation
            self.previous_record_value = value
            return ''
        else: # get operation
            return self.previous_record_value

    def get_date(self, ):
        """ For report time
        """
        return datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def get_table(self, table):
        """ Return frames object:
        """
        return eval('self.%s' % table)

    # TODO remove when removed from all report (use get_table)
    def get_frames(self, ):
        """ Return frames object:
        """
        return self.frames

    def get_materials(self, mrp_id):
        """ Return materials object:
        """
        res = []

        # TODO check procedure:
        for component in sorted(
                self.material_db, key=lambda x: x.default_code):
            stock = component.mx_net_mrp_qty
            current = self.material_db[component]
            future = component.mx_mrp_future_qty
            # -current#XXX WAS: without this
            # available = stock - future
            # if not current:
            #    cut = 0
            # elif available:
            #    cut = available #XXX WAS: current - available
            #    # in negative no cut:
            #    if cut < 0:
            #        cut = 0
            # else:
            #    cut = current

            # Load other MO (not this)
            production_list = set(
                [('%s ' % (c.mrp_id.name or 'OC')).replace(
                    'MO', '').lstrip('0')
                    for c in component.future_ids if
                    c.mrp_id.id != mrp_id])

            res.append((
                component,  # Component
                int(current),  # This MRP
                int(stock),  # Stock
                int(future),  # MRP open
                0,  # XXX int(cut), # Cut net
                production_list,  # List of production
                ))
        return res

    def get_object_with_total_cut(self, o, data=None):
        """ Get object with totals for normal report
            Sort for [4:6]-[9:12]
            Break on 2 block for total
        """
        def add_material_cut(product, material_db, todo, product_components):
            """ Add product in database for add on report
                line: mrp.bom.line element
                material_db: database for report
                product_components: for save component in product
            """
            for bom in product.dynamic_bom_line_ids:
                if bom.category_id.department != 'cut':
                    continue  # only category element with department cut

                component = bom.product_id

                # -------------------------------------------------------------
                # Product component management
                # -------------------------------------------------------------
                if component.bom_placeholder or component.bom_alternative:
                    # Not used placeholder
                    continue

                if product not in product_components:
                    product_components[product] = {}

                if component not in product_components[product]:
                    component_qty = bom.product_qty
                    product_components[product][component] = {}
                    for fabric in component.half_bom_ids:
                        fabric_code = fabric.product_id.default_code or ''
                        if fabric_code[:1].upper() == 'T':
                            product_components[product][component][
                                fabric_code] = (fabric.product_qty *
                                                component_qty)
                        else:
                            _logger.warning('Jumped %s' % fabric_code)

                todo_q = todo * bom.product_qty  # Remain total
                if component in material_db:
                    material_db[component] += todo_q
                else:
                    material_db[component] = todo_q

        if data is None:
            data = {}
        mode = data.get('mode', 'clean')

        lines = []
        for line in sorted(
                o.order_line_ids,
                key=lambda item: (
                    item.product_id.default_code[3:6],
                    item.product_id.default_code[8:12],
                    item.product_id.default_code[0:3],
                    )):
            lines.append(line)

        # Total for code break:
        code1 = code2 = False
        total1 = total2 = 0.0
        records = []

        self.mrp_sol = []  # Note management
        self.frames = {}
        self.material_db = {}  # Database for next report
        self.product_components = {}  # Database for product component
        for line in lines:  # sale order line
            default_code = line.default_code

            # Variable:
            product_uom_qty = line.product_uom_qty  # OC
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty  # B
            delivered_qty = line.delivered_qty  # Del.

            # Consider OC as OC - assigned = net production:
            mx_assigned_qty = line.mx_assigned_qty
            product_uom_qty -= mx_assigned_qty

            if mode == 'clean':  # remove delivered qty (OC and Maked)
                product_uom_qty -= delivered_qty
                product_uom_maked_sync_qty -= delivered_qty
                if not product_uom_qty:
                    continue  # jump empty line

                if product_uom_maked_sync_qty < 0:  # remain 0 if negative
                    product_uom_maked_sync_qty = 0.0
                elif product_uom_maked_sync_qty > 0:  # clean ordered with done
                    product_uom_qty -= product_uom_maked_sync_qty
                    if not product_uom_qty:
                        continue  # jump empty line
                    product_uom_maked_sync_qty = 0.0
                todo = product_uom_qty  # for next report
            else:  # normal mode
                if product_uom_maked_sync_qty >= delivered_qty:
                    todo = product_uom_qty - product_uom_maked_sync_qty
                else:
                    todo = product_uom_qty - delivered_qty

            # Total operations:
            # if not line.order_id.mx_closed: # only for not closed order
            self.report_extra_data['total_qty'] += product_uom_qty
            self.report_extra_data['done_qty'] += product_uom_maked_sync_qty

            add_material_cut(
                line.product_id, self.material_db, todo,
                self.product_components)

            # -------------
            # Check Frames:
            # -------------
            # France total:
            frame = default_code.replace(' ', '.')[6:8]
            if frame not in self.frames:
                self.frames[frame] = 0.0
            self.frames[frame] += product_uom_qty

            # -----------------
            # Check for totals:
            # -----------------
            # Color total:
            color = default_code[8:12].rstrip()
            if code1 == False:  # XXX first loop
                total1 = 0.0
                code1 = color

            if code1 == color:
                total1 += product_uom_qty
            else:
                code1 = color

                # Add extra line for BOM status:
                records.append(('T1', line, total1))
                total1 = product_uom_qty

            # Code general total:
            if code2 == False:  # XXX first loop
                total2 = 0.0
                code2 = default_code

            if code2 == default_code:
                total2 += product_uom_qty
            else:
                code2 = default_code
                records.append(('T2', line, total2))
                total2 = product_uom_qty

            # -------------------
            # Append record line:
            # -------------------
            records.append(('L', line, False))
            self.mrp_sol.append(line)

        # Append last totals if there's records:
        if records:
            records.append(('T1', line, total1))
            records.append(('T2', line, total2))

        self.report_extra_data['records'] = records
        return records

    def setup_data_cut(self, o, data=None):
        """ Setup data and totals
        """
        self.report_extra_data = {
            'records': False,
            'total_qty': 0.0,
            'done_qty': 0.0,
            }
        self.get_object_with_total_cut(o, data=data)

    def setup_data_mrp(self, o, data=None):
        """ Setup data and totals
        """
        self.report_extra_data = {
            'records': False,
            'total_qty': 0.0,
            'done_qty': 0.0,
            }

        self.get_object_with_total(o, data=data)

    def get_report_extra_data(self, field):
        """ Return extra data report same for mrp and cut
        """
        localcontext = self.localcontext.get('data', {})
        report_name = localcontext.get('report_name')
        if field == 'records' and report_name == 'mrp':
            if localcontext['report_filename']:
                # Export data in Excel file:
                self.extract_report_for_sl(
                    self.cr,
                    self.uid,
                    self.report_extra_data.get(field, ''),
                    {})

        return self.report_extra_data.get(field, '')

    def extract_report_for_sl(self, cr, uid, data, context=None):
        """ Extract report for SL production
        """
        excel_pool = self.pool.get('excel.writer')

        localcontext = self.localcontext.get('data', {})

        ws_name = 'Dettaglio produzione'
        excel_pool.create_worksheet(ws_name)
        filename = localcontext.get('report_filename')

        # ---------------------------------------------------------------------
        # Format:
        # ---------------------------------------------------------------------
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        format_number = excel_pool.get_format('number')

        # ---------------------------------------------------------------------
        # Column dimension:
        # ---------------------------------------------------------------------
        col_width = (
            5, 10,
            30,
            12, 10, 30,
            10, 10, 10, 10)
        excel_pool.column_width(ws_name, col_width)

        # Row 1
        row = 0
        header = [
            'Riferimento OC', '',
            'Cliente',
            'Prodotto', 'Scadenza OC', 'Note di produzione',
            'Pz./Imb', 'Bancale', 'Da fare', 'Fatti',
            ]

        excel_pool.write_xls_line(
            ws_name, row, header, format_header)
        excel_pool.merge_cell(ws_name, [row, 0, row, 1])

        for mode, line, total in data:
            if mode != 'L':
                continue

            row += 1
            code = line.product_id.default_code or ''
            record = [
                line.mrp_sequence,
                self.clean_order(line.order_id.name),
                line.order_id.partner_id.name,
                '%s%s' % (
                    line.product_id.default_code.replace(' ', '.') or '',
                    ' (PREVIS.)' if line.order_id.forecasted_production_id
                    else '',
                    ),
                # formatLang(line.date_deadline,
                #           date=True) if line.date_deadline else ""
                line.date_deadline or '',
                '%s %s %s' % (
                    'IGNIFUGO ' if code[5:6].upper() == 'I' else '',
                    self.clean_note(line.production_note),
                    (line.order_id.client_order_ref or '').split('|')[-1]
                    ),
                int(line.product_id.q_x_pack),
                'EUR' if line.order_id.partner_id.pallet_eur else '',
                int(total[0]),
                int(total[1]) if total[1] else '',
            ]
            excel_pool.write_xls_line(
                ws_name, row, record, format_text)

        _logger.info('Saving extra file in %s' % filename)
        return excel_pool.save_file_as(filename)

    def get_object_with_total(self, o, data=None):
        """ Get object with totals for normal report
        """
        # Pool used:
        mrp_pool = self.pool.get('mrp.production')
        job_pool = self.pool.get('mrp.production.stats')

        # Default args:
        cr = self.cr
        uid = self.uid
        context = {'lang': 'it_IT'}
        if data is None:
            data = {}

        # Mode (and Job mode):
        mode = data.get('mode', 'clean')
        job_id = data.get('wizard_job_id')
        if job_id:
            job = job_pool.browse(cr, uid, job_id, context=context)
            sorted_lines = sorted(
                job.working_ids, key=lambda x: x.mrp_sequence)
            # mode = 'all'
        else:
            sorted_lines = o.sort_order_line_ids

        lines = []
        for line in sorted_lines:  # jet ordered:
            lines.append(line)

        # Total for code break:
        code1 = False  # code2 =
        total1 = 0.0  # total2 =
        records = []

        # ---------------------------------------------------------------------
        # Database for table summary:
        # ---------------------------------------------------------------------
        # Simple dictionary:
        self.parents = {}
        self.frames = {}
        self.parent_frame = {}
        self.fabric_color = {}
        self.packages = {}

        # Table dictionary:
        self.parent_frame_table = {}
        self.mrp_sol = []
        old_line = False
        for line in lines:
            default_code = line.default_code

            if job_id:  # Force for Job q. if present
                job_uom_qty = line.job_uom_qty
            else:
                job_uom_qty = 0

            # Read Qty with standard function:
            reply = mrp_pool.get_mrp_oc_maked_qty_from_line(
                line, mode, job_uom_qty)
            if not reply:  # Line not needed in print (clean mode)!
                continue

            # Extract data from call:
            product_uom_qty = reply.get('total', 0.0)
            product_uom_maked_sync_qty = reply.get('done', 0.0)

            # Total operations:
            self.report_extra_data['total_qty'] += product_uom_qty
            self.report_extra_data['done_qty'] += product_uom_maked_sync_qty

            # -----------------------------------------------------------------
            #                     COLLECT SUMMARY DATA:
            # -----------------------------------------------------------------
            # 0. Code part:
            parent = default_code[:3]
            fabric = default_code[3:6].replace(' ', '.')
            frame = default_code[6:8].replace(' ', '.')
            color = default_code[8:12].rstrip()
            fabric_color = '%s -- %s' % (fabric, color)
            package = default_code[12:13].upper()

            q_x_pack = int(line.product_id.q_x_pack)
            if package == 'S':
                package = '(S)INGOLO'
            else:
                package = False

            # -----------------------------------------------------------------
            #                           Total:
            # -----------------------------------------------------------------
            # 1. Parent total:
            if parent not in self.parents:
                self.parents[parent] = 0.0
            self.parents[parent] += product_uom_qty

            # 2. Fabric - Color Total:
            if fabric_color not in self.fabric_color:
                self.fabric_color[fabric_color] = 0.0
            self.fabric_color[fabric_color] += product_uom_qty

            # 3. Frames total:
            if frame not in self.frames:
                self.frames[frame] = 0.0
            self.frames[frame] += product_uom_qty

            # 4. Package:
            if package:
                if package not in self.packages:
                    self.packages[package] = 0.0
                self.packages[package] += product_uom_qty

            # 5. Table: Parent + Frame
            key = (parent, frame)
            if key not in self.parent_frame_table:
                self.parent_frame_table[key] = 0.0
            self.parent_frame_table[key] += product_uom_qty

            # -----------------------------------------------------------------
            # Check for totals:
            # -----------------------------------------------------------------
            # Color total:
            if code1 == False:  # XXX first loop
                total1 = 0.0
                code1 = default_code  # parent #color

            if code1 == default_code:  # parent: #color:
                total1 += product_uom_qty
            else:
                code1 = default_code  # parent #color
                records.append(('T1', old_line, total1))
                total1 = product_uom_qty

            # -----------------------------------------------------------------
            # Code general total:
            # -----------------------------------------------------------------
            # XXX is T2 used?
            # if code2 == False: # XXX first loop
            #    total2 = 0.0
            #    code2 = default_code

            # if code2 == default_code:
            #    total2 += product_uom_qty
            # else:
            #    code2 = default_code
            #    records.append(('T2', old_line, total2))
            #    total2 = product_uom_qty

            # -------------------
            # Append record line:
            # -------------------
            records.append(
                ('L', line, (
                    product_uom_qty, product_uom_maked_sync_qty,
                    )))
            old_line = line
            self.mrp_sol.append(line) # for note system

        # Append last totals if there's records:
        if records:
            records.append(('T1', old_line, total1))
            # records.append(('T2', old_line, total2))

        self.report_extra_data['records'] = records

        # ---------------------------------------------------------------------
        # Prepare table for parent frame calls:
        # ---------------------------------------------------------------------
        self.parent_frame_clean = []
        for parent in sorted(self.parents):
            record = [parent, int(self.parents[parent])]
            for frame in sorted(self.frames):
                key = (parent, frame)
                if key in self.parent_frame_table:
                    record.append(self.parent_frame_table[key])
                else:
                    record.append('')
            self.parent_frame_clean.append(record)

        return records  # todo remove?

    def get_object_remain(self, ):
        """ Get as browse obj all record with unsync elements
        """
        line_ids = self.pool.get('sale.order.line').search(self.cr, self.uid, [
            ('product_uom_maked_qty', '>', 0.0)], order='order_id')
        return self.pool.get('sale.order.line').browse(
            self.cr, self.uid, line_ids)

    def get_hour(self, value):
        """ Format float with H:MM format
        """
        try:
            return "%s:%s" % (
                int(value),
                int(60 * (value - int(value))),
                )
        except:
            return "0:00"


class MrpProductionInherit(orm.Model):
    """ Save used function
    """
    _inherit = 'mrp.production'

    def get_mrp_oc_maked_qty_from_line(self, line, mode, job_uom_qty):
        """ Extract line data from MRP information
        """
        # Parameters:
        product_uom_qty = line.product_uom_qty
        product_uom_maked_sync_qty = line.product_uom_maked_sync_qty

        # Consider OC as OC - assigned = net production:
        mx_assigned_qty = line.mx_assigned_qty
        product_uom_qty -= mx_assigned_qty

        # ---------------------------------------------------------------------
        # Or Job mode XOR clean mode!
        # ---------------------------------------------------------------------
        if job_uom_qty:  # Job mode:
            product_uom_qty = job_uom_qty  # Forceq q.
            product_uom_maked_sync_qty = 0.0  # All to produce!

        elif mode == 'clean':  # remove delivered qty (OC and Maked)
            delivered_qty = line.delivered_qty
            product_uom_qty -= delivered_qty
            product_uom_maked_sync_qty -= delivered_qty

            if not product_uom_qty:
                return False  # jump empty line

            if product_uom_maked_sync_qty < 0:  # remain 0 if negative
                product_uom_maked_sync_qty = 0.0
            elif product_uom_maked_sync_qty > 0:  # clean ordered with done
                product_uom_qty -= product_uom_maked_sync_qty
                if not product_uom_qty:
                    return False  # jump empty line
                product_uom_maked_sync_qty = 0.0

        return {
            'total': product_uom_qty,
            'done': product_uom_maked_sync_qty
        }
