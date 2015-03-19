#!/usr/bin/python
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
import ConfigParser
from datetime import datetime
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler


# -----------------------------------------------------------------------------
#                                Parameters
# -----------------------------------------------------------------------------

config = ConfigParser.ConfigParser()
config.read(['./openerp.cfg'])

# XMLRPC server:
xmlrpc_host = config.get('XMLRPC', 'host') 
xmlrpc_port = eval(config.get('XMLRPC', 'port'))

path = config.get('mexal', 'path')
exchange_file = config.get('mexal', 'exchange_file')
company_code = config.get('mexal', 'company')

# Access:
mx_user = config.get('mexal', 'user')
mx_password = config.get('mexal', 'password')

# Sprix:
sprix_production = eval(config.get('mexal', 'sprix_production'))

# Parameters calculated:
# Transit files:
file_production = os.path.join(path, "production", exchange_file)
path_history = os.path.join(path, "production", "history")

sprix_command = r"%s\mxdesk.exe -command=mxrs.exe -login=%s -t0 -x2 win32g -p#%s -a%s -k%s:%s" % (
    path, 
    mx_user, # login
    "%s", # sprix
    company_code, # sign company 
    mx_user, # user for login
    mx_password, # password
    )

# -----------------------------------------------------------------------------
#                         Restrict to a particular path
# -----------------------------------------------------------------------------
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# -----------------------------------------------------------------------------
#                                Create server
# -----------------------------------------------------------------------------
server = SimpleXMLRPCServer(
    (xmlrpc_host, xmlrpc_port), requestHandler=RequestHandler)
server.register_introspection_functions()

# -----------------------------------------------------------------------------
#                                 Functions
# -----------------------------------------------------------------------------
def sprix(operation, parameters=None):
    ''' Call mxrs program passing sprix number
    '''
    if parameters is None:
        parameters = {}
        
    # -------------------------------------------------------------------------
    #                        Cases (operations):
    # -------------------------------------------------------------------------    
    if operation.upper() == "production": 
        # -------------------------------
        # Tranform passed string to file:
        # -------------------------------
        string = parameters.get(string2file, False)
        if not string:
            return "#ERR No file passed"            
        try:
            res_file = open(file_production, "w")
            res_file.write(string)
            res_file.close()
        except:
            return "#ERR Opening/creating transit file: %s" % file_production
    
        # ---------------------------------
        # Call sprix for create production:
        # ---------------------------------
        try:
            command = sprix_command % sprix_production
            os.system(command)
        except:
            return "#ERR Launch sprix command: %s" % command

        # -------------------------
        # Read result of operation:
        # -------------------------
        completed = []
        try:
            for line in open(file_production, "r"):
                if line[45:47] == 'OK': # TODO Change
                    completed.append(int(line[50:60].strip()))
        except:
            return "#ERR Error read result of operation"

        # ----------------------------------
        # History files and clean temporary:
        # ----------------------------------
        try: 
            os.move(
                transit_file, 
                os.path.join(
                    path_history, 
                    datetime.now().strftime("%Y%m%d.%H%M%s.txt"),
                    )
            
        
    return False # normal operations

# -----------------------------------------------------------------------------
#                  Register Function in XML-RPC server:
# -----------------------------------------------------------------------------
server.register_function(sprix, 'sprix')

# -----------------------------------------------------------------------------
#                       Run the server's main loop:
# -----------------------------------------------------------------------------
server.serve_forever()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
