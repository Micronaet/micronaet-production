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

class ReportStatusWork(models.AbstractModel):
    ''' Report parser status of work
    '''
    _name = 'report.production_working_bom.report_status_work'
    
    @api.multi
    def render_html(self, data=None):
        ''' Renter report action:
        '''
        report_obj = self.env['report']
        report = report_obj._get_report_from_name(
            'production_working_bom.report_status_work')
        docargs = {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': self,
            }
            
        # Add context elements:
        #ctx = dict(self._context)
        #ctx['translatable'] = True
        #report_obj = report_obj.with_context(ctx)
                    
        return report_obj.render(
            'production_working_bom.report_status_work', 
            docargs, 
            )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

