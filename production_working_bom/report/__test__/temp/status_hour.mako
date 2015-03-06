<html>
<head>
    <style type="text/css">
        ${css}

        /*Colori utilizzati:
          #a7aeb8 blu celeste
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
            font-weight:bold;
        }
        .yellow {
            background-color:#fffccc;
            font-weight:bold;
        }
        .white {
            background-color:#ffffff;
            font-weight:bold;
        }
        .light_blue {
            background-color:#dddddd;
            font-weight:bold;
        }
        .fg_white {
            color:#ffffff;
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
            vertical-align:top;
            border:1px solid #000;             
            padding:0px;
            margin:0px;                        
            cellspacing:0px;
            cellpadding:0px;
            border-collapse:collapse;
            
            /*Non funziona il paginate*/
            -fs-table-paginate: paginate;
        }

        .invisible {
            border:0px solid #000;             
            padding:0px;
            margin:0px;                        
            cellspacing:0px;
            cellpadding:0px;
            border-collapse:collapse;
            /*Non funziona il paginate*/
            -fs-table-paginate: paginate;
        }

        table.list_table tr, table.list_table tr td {
            vertical-align:top;
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
              width:100px;
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
           <% thead = "<thead><tr><th class='description fg_white'>%s</th>%s</tr></thead>" %>                  
           <% thead_internal="" %>
               %for col in get_cols():                       
                    <% thead_internal += "<th class='data fg_white'>%s</th>"%(col,) %>                      
               %endfor
           ${thead % ("Linee", thead_internal,)}

         <!-- ################## BODY ##################################### -->
          <tbody>
              <% i=0 %>
              <% rows = get_rows()%>
              <% total_cols = {}%>
              %for row in rows:
                  <tr>
                    <td class="description">${row}</td>
                    % for col in get_cols():
                         <% (hm, hour, products) = get_cel(row, col) %>
                         <% total_cols[col] = total_cols.get(col, 0.0) + hm %>
                         <% class_color = "data white" %>
                         <td>
                            <table class="invisible"><tr>
                                 %if hour <= 0:    # > 8  (white)
                                     <td class = "${class_color}">&nbsp;</td>
                                 %elif hour <= 8.0:    # > 8  (green)
                                     %if hour:
                                         <% class_color = "data green" %>
                                     %endif    
                                     <td class = "${class_color}">H.: ${hour|entity}</td>
                                 %elif hour > 8.0 and hour <=9: # extra time (yellow)
                                     %if hour:
                                         <% class_color = "data yellow"%>
                                     %endif    
                                     <td class = "${class_color}">H.: ${hour|entity}</td>
                                 %elif hour > 9.0: # over time (red)
                                     %if hour:
                                         <% class_color = "data red"%>
                                     %endif    
                                     <td class = "${class_color}">H.: ${hour|entity}</td>
                                 %endif
                                 </tr>
                                 <tr>
                                 %if hm > 0:
                                     <td class = "data white">H/u.: ${hm|entity}</td>
                                 %else:
                                     <td class = "data white">&nbsp;</td>
                                 %endif    
                            <tr>
                                %if products:
                                    <td class = "data light_blue">
                                        %for p in products:
                                            ${"%s" % p.replace(" ", "")|entity}
                                        %endfor
                                    </td>
                                %else:
                                    <td class = "data white">&nbsp;</td>
                                %endif
                            </tr>
                            </tr></table>
                         </td>
                    % endfor
                  </tr>
                  <% i += 1 %>
              %endfor  
              <!--TOTALS:-->
              <tr>
                    <td class="description">Totale H/u:</td>
                    % for col in get_cols():
                        <% tot = total_cols[col] %>
                         %if tot <= 0:                     # null
                             <td class = "data white">${tot|entity}</td>
                         %elif tot <= 80.0:                # normal
                             <td class = "data green">${tot|entity}</td>
                         %elif tot > 80.0 and tot <=90.0:  # extra time
                             <td class = "data yellow">${tot|entity}</td>
                         %elif tot > 25:                   # over time
                             <td class = "data red">${tot|entity}</td>
                         %endif
                    %endfor 
              </tr>        
          </tbody>
     </table>     
</body>
</html>
