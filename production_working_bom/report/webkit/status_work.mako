<html>
<head>
    <style type="text/css">
        ${css}

        /*Colori utilizzati:
          #b7bec8 blu celeste
          #f6cf3b giallo
          #7c7bad violetto
          #444242 grigio scuro
        */

        p {
           margin:2px;
        }
        h2 {
            font-size:13px;            
        }

        .red {
            background-color:#ffd5d5;
            /*A70010;*/
            font-weight:bold;
        }
        .blu {
            background-color:#d5e9ff;
            /*363AA7;*/
            font-weight:bold;
        }
        .green {
            background-color:#ade3b8;
            /*004E00;*/
            font-weight:bold;
        }
        .yellow {
            background-color:#fffccc;
            /*004E00;*/
            font-weight:bold;
        }
        
        .right {
            text-align:right;         
        }
        .center {
            text-align:center;
        }
        .left {
            text-align:left;
        }
        .even {
            background-color: #efeff8;
        }
        .odd {
            background-color: #FFFFFF;
        }
        
        .total {
            font-size:11px;          
            font-weight:bold;  
            padding:4px;
            background-color: #f6cf3b;
        }
        
        .center_line {
            text-align:center; 
            border:1px solid #000; 
            padding:3px;
        }

        table.list_table {
            border:1px solid #000;             
            padding:0px;
            margin:0px;                        
            cellspacing:0px;
            cellpadding:0px;
            border-collapse:collapse;
            
            /*Non funziona il paginate*/
            -fs-table-paginate: paginate;
        }

        table.list_table tr, table.list_table tr td {
            page-break-inside:avoid;
        }        
        
        thead tr th{
            text-align:center;
            font-size:10px;
            border:1px solid #000; 
            background:#7c7bad;            
        }
        thead {
            display: table-header-group;
            }
            
        tbody tr td{
            text-align:center;
            font-size:10px;
            border:1px solid #000; 
        }
        .description{
              width:250px;
              text-align:left;
        }
        .data{
              width:50px;
              vertical-align:top;
              font-size:8px;          
              font-weight:normal;
              /*color: #000000;*/
        }
        .nopb {
            page-break-inside: avoid;
           }
    </style>
</head>
<body>
   <% setLang('it_IT') %>
   <% start_up(data) %>
   <!-- Start loop for design table for product and material status: -->
     <table class="list_table">      
         <!-- ################## HEADER ################################### -->
           <% thead = "<thead><tr><th class='description'>%s</th>%s</tr></thead>" %>                  
           <% thead_internal="" %>
               %for col in get_cols():                       
                    <% thead_internal += "<th class='data'>%s</th>"%(col,) %>                      
               %endfor
           ${thead % ("Material", thead_internal,)}

         <!-- ################## BODY ##################################### -->
          <tbody>
              <% i=0 %>
              <% rows = get_rows()%>
              %for row in rows:
                  % if not jump_is_all_zero(row[1], data):
                      <% status_line = 0.0 %>
                      <tr>
                        <td class="description">${row[0].split(": ")[1]}</td>
                        <% j = 0 %>
                        % for col in get_cols():
                             <% (q, minimum) = get_cel(j, row[1]) %>
                             <% j += 1 %>
                             <% status_line += q %>
                              %if not status_line:            # value = 0
                                  <td class = "data">${status_line|entity}</td>
                              %elif status_line > minimum:    # > minimum value (green)
                                  <td class = "data green">${status_line|entity}</td>
                              %elif status_line > 0.0:        # under minimum (yellow)
                                  <td class = "data yellow">${status_line|entity}</td>
                              %elif status_line < 0.0:        # under 0 (red)
                                  <td class = "data red">${status_line|entity}</td>
                              %else: # ("=", "<"):             # not present!!!
                                  <td class = "data">${status_line|entity}</td>
                              %endif
                        % endfor
                      </tr>
                      <% i += 1 %>
                  % endif   
              %endfor          
          </tbody>
     </table>     
</body>
</html>
