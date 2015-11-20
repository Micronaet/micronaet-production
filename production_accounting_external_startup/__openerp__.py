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

{
    'name': 'Production accounting external startup',
    'version': '0.1',
    'category': 'Startup',
    'description': '''  
        This module create a fax production where put all family lines that
        are yet produced in initial phase.
        Production order are minimal and has only lines that are produced or
        delivered, information readed from accounting code.
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'production_accounting_external',
        'accounting_statistic_order', # For get text file with order closed        
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        #'security/ir.model.access.csv',    
        'startup_view.xml', # after wizard 
        'scheduler.xml',     
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
