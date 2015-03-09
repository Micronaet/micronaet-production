# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) and the
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#    ########################################################################
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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


from openerp import api, models

class ReportStatusHour(models.AbstractModel):
    ''' Report parser status of hour
    '''
    
    _name = 'report.production_working_bom.report_status_hour'
    
    # -------------------------------------------------------------------------
    # Render method:
    # -------------------------------------------------------------------------
        
    @api.multi
    def render_html(self, data=None):
        ''' Renter report action:
        '''
        # ---------------------------------------------------------------------
        # Set up private variables:
        # ---------------------------------------------------------------------
        self.rows = []
        self.cols = []
        self.minimum = {}
        self.table = {}
        self.counter = {} # counter dict
        
        report_obj = self.env['report']
        report = report_obj._get_report_from_name(
            'production_working_bom.report_status_hour')
        docargs = {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': self,
            
            # Counters:
            'get_dict_counter': self.get_dict_counter,
            'set_dict_counter': self.set_dict_counter,

            # Report:
            'startup': self._startup,
            'get_rows': self._get_rows,
            'get_cols': self._get_cols,
            'get_cel': self._get_cel,
            'has_negative': self._has_negative,            
            
            # Color element:
            'get_wh': self.get_wh,
            }
        return report_obj.render(
            'production_working_bom.report_status_hour', 
            docargs, 
            )

    def get_wh(self, ):
        ''' Read company element with 
        '''
        company_proxy = self.pool.get('res.company').get_hour_parameters(
            self.env.cr, self.env.uid)
        return (
            company_proxy.work_hour_day,
            company_proxy.work_hour_day + company_proxy.extra_hour_day,
            company_proxy.work_hour_day * company_proxy.employee,
            company_proxy.employee * (
                company_proxy.extra_hour_day + company_proxy.work_hour_day),
            )

    # -------------------------------------------------------------------------
    # Counters methods:
    # -------------------------------------------------------------------------
    # Dict:
    def set_dict_counter(self, name, item, value=False, with_return=False):
        ''' Set element of dict counter
        '''
        # Fast setup of counter if not present
        if name not in self.counter:
            self.counter[name] = {}
        self.counter[name][item] = value
        if with_return:
            return value
        else: # nothing returned    
            return ""

    def get_dict_counter(self, name, item, default=False):
        ''' Get element of counter:
        '''
        # Fast setup of counter if not present
        if name not in self.counter:
            self.counter[name] = {}
        if item not in self.counter[name]:
            # Fast set of default creating elements:
            self.counter[name][item] = default
        return self.counter[name][item]
        
    # -------------------------------------------------------------------------
    # Report methods:
    # -------------------------------------------------------------------------
    def _has_negative(self, row, data=None):
        ''' ???
        '''
        return 
        
    def _startup(self, data=None):
        ''' Master function for prepare report
        '''
        if data is None:
            data = {}
                    
        # initialize globals:
        self.rows = []
        self.cols = []
        self.table = {}
        self.counters = {}
        
        # Load production converter for get product code:
        production_pool = self.pool.get("mrp.production")
        production_ids = production_pool.search(self.env.cr, self.env.uid, [])
        production_converter = {}
        
        for p in production_pool.browse(
                self.env.cr, self.env.uid, production_ids):
            production_converter[p.id] = (
                p.product_id.default_code or p.product_id.name or "#NoCod")
                
        # Read cols elements:        
        self.env.cr.execute("""
            SELECT DISTINCT left(CAST(date_planned AS TEXT), 10) as day
            FROM mrp_production_workcenter_line
            ORDER BY day;
            """)
        for day in self.env.cr.fetchall():
            day = day[0]
            self.cols.append(day[-5:]) # populare cols list
            
            start = "%s 00:00:00" % day
            end = "%s 23:59:59" % day
            
            self.env.cr.execute("""
                SELECT rr.name, q.hour, q.workers, q.prod 
                FROM (
                    SELECT 
                        workcenter_id AS wc, 
                        sum(hour) AS hour, 
                        min(workers) AS workers,
                        production_id AS prod 
                    FROM mrp_production_workcenter_line 
                    WHERE date_planned >= %s and date_planned <= %s 
                    GROUP BY workcenter_id, production_id, workers) AS q 
                    
                    JOIN mrp_workcenter wc ON (q.wc = wc.id) 
                    JOIN resource_resource rr ON (wc.resource_id = rr.id) 
                    ORDER BY rr.name;
                """, (start, end))

            for record in self.env.cr.fetchall():
                if record[0] not in self.rows:
                    self.rows.append(record[0])
                    
                k = (record[0], day[-5:]) # key for table elements
                if k not in self.table:
                    # Set up initial value
                    self.table[k] = [
                        0.0, # Hour / man
                        0.0, # Total line hour
                        [], # Products
                        ]

                self.table[k][0] += record[1] * record[2]
                self.table[k][1] += record[1]
                self.table[k][2].append(
                    production_converter.get(record[3], "??")) # production_id > default_code
                
        self.rows.sort() # only row
        return True

    def _get_rows(self):
        ''' Rows list (generated by _start_up function)
        '''
        return self.rows

    def _get_cols(self):
        ''' Cols list (generated by _start_up function)
        '''
        return self.cols

    def _get_cel(self, row, col):
        ''' Return cell elements or empty one if not present
        '''
        return self.table.get((row, col), [0, 0, []])
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

