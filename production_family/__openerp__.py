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
    'name': 'Product family',
    'version': '0.1',
    'category': '',
    'description': """
        In production sometimes is usefull act with family of product than
        product so this module create a particular product that work like
        goups (the difference is that when you product, create a BOM,
        sell generic product etc. you can use directly the product instead of
        change all linked object to work with groups.
        """,
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'product',
        'mrp',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'family_views.xml',        
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
