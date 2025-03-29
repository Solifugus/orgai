#!/usr/bin/env python3

import os
import yaml
import pyodbc
from datetime import datetime
from typing import Dict, List, Any
import re

class DatabaseDocGenerator:
    def __init__(self):
        self.config = self._load_config()
        self.connections = {}
        self._initialize_connections()
        
    def _load_config(self) -> Dict:
        """Load configuration from config.yaml"""
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    
    def _initialize_connections(self):
        """Initialize database connections"""
        base_conn_str = self.config['sql_server']['connection_string']
        excluded_schemas = self.config['sql_server']['excluded_schemas']
        
        for db in self.config['sql_server']['databases']:
            conn_str = f"{base_conn_str};Database={db}"
            try:
                conn = pyodbc.connect(conn_str)
                self.connections[db] = {
                    'connection': conn,
                    'excluded_schemas': excluded_schemas
                }
            except Exception as e:
                print(f"Error connecting to {db}: {e}")
    
    def _get_tables(self, db_name: str) -> List[Dict]:
        """Get all tables in a database"""
        conn = self.connections[db_name]['connection']
        excluded_schemas = self.connections[db_name]['excluded_schemas']
        
        query = """
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_TYPE,
            p.value as DESCRIPTION
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.extended_properties p ON 
            p.major_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
            AND p.minor_id = 0
            AND p.name = 'MS_Description'
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        AND t.TABLE_SCHEMA NOT IN ({})
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """.format(','.join(['?'] * len(excluded_schemas)))
        
        cursor = conn.cursor()
        cursor.execute(query, excluded_schemas)
        return [dict(zip([column[0] for column in cursor.description], row))
                for row in cursor.fetchall()]
    
    def _get_columns(self, db_name: str, schema: str, table: str) -> List[Dict]:
        """Get all columns in a table"""
        conn = self.connections[db_name]['connection']
        
        query = """
        SELECT 
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.IS_NULLABLE,
            p.value as DESCRIPTION,
            c.COLUMN_DEFAULT,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN sys.extended_properties p ON 
            p.major_id = OBJECT_ID(? + '.' + ?)
            AND p.minor_id = c.ORDINAL_POSITION
            AND p.name = 'MS_Description'
        WHERE c.TABLE_SCHEMA = ?
        AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (schema, table, schema, table))
        return [dict(zip([column[0] for column in cursor.description], row))
                for row in cursor.fetchall()]
    
    def _get_views(self, db_name: str) -> List[Dict]:
        """Get all views in a database"""
        conn = self.connections[db_name]['connection']
        excluded_schemas = self.connections[db_name]['excluded_schemas']
        
        query = """
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            v.VIEW_DEFINITION,
            p.value as DESCRIPTION
        FROM INFORMATION_SCHEMA.VIEWS v
        JOIN INFORMATION_SCHEMA.TABLES t ON 
            v.TABLE_SCHEMA = t.TABLE_SCHEMA 
            AND v.TABLE_NAME = t.TABLE_NAME
        LEFT JOIN sys.extended_properties p ON 
            p.major_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
            AND p.minor_id = 0
            AND p.name = 'MS_Description'
        WHERE t.TABLE_SCHEMA NOT IN ({})
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """.format(','.join(['?'] * len(excluded_schemas)))
        
        cursor = conn.cursor()
        cursor.execute(query, excluded_schemas)
        return [dict(zip([column[0] for column in cursor.description], row))
                for row in cursor.fetchall()]
    
    def _get_stored_procedures(self, db_name: str) -> List[Dict]:
        """Get all stored procedures in a database"""
        conn = self.connections[db_name]['connection']
        excluded_schemas = self.connections[db_name]['excluded_schemas']
        
        query = """
        SELECT 
            p.SPECIFIC_SCHEMA,
            p.SPECIFIC_NAME,
            p.PARAMETER_MODE,
            p.PARAMETER_NAME,
            p.DATA_TYPE,
            p.PARAMETER_DEFAULT,
            p.ORDINAL_POSITION,
            p.IS_RESULT,
            p.AS_LOCATOR,
            p.CHARACTER_MAXIMUM_LENGTH,
            p.CHARACTER_OCTET_LENGTH,
            p.NUMERIC_PRECISION,
            p.NUMERIC_SCALE,
            p.DATETIME_PRECISION,
            p.INTERVAL_TYPE,
            p.INTERVAL_PRECISION,
            p.USER_DEFINED_TYPE_CATALOG,
            p.USER_DEFINED_TYPE_SCHEMA,
            p.USER_DEFINED_TYPE_NAME,
            p.SCOPE_CATALOG,
            p.SCOPE_SCHEMA,
            p.SCOPE_NAME,
            p.MAXIMUM_CARDINALITY,
            p.DTD_IDENTIFIER,
            p.IS_SENSITIVE,
            sp.definition as PROCEDURE_DEFINITION,
            ep.value as DESCRIPTION
        FROM INFORMATION_SCHEMA.PARAMETERS p
        JOIN sys.sql_modules sp ON 
            OBJECT_ID(p.SPECIFIC_SCHEMA + '.' + p.SPECIFIC_NAME) = sp.object_id
        LEFT JOIN sys.extended_properties ep ON 
            ep.major_id = OBJECT_ID(p.SPECIFIC_SCHEMA + '.' + p.SPECIFIC_NAME)
            AND ep.minor_id = 0
            AND ep.name = 'MS_Description'
        WHERE p.SPECIFIC_SCHEMA NOT IN ({})
        ORDER BY p.SPECIFIC_SCHEMA, p.SPECIFIC_NAME, p.ORDINAL_POSITION
        """.format(','.join(['?'] * len(excluded_schemas)))
        
        cursor = conn.cursor()
        cursor.execute(query, excluded_schemas)
        return [dict(zip([column[0] for column in cursor.description], row))
                for row in cursor.fetchall()]
    
    def _generate_html(self, db_name: str):
        """Generate HTML documentation for a database"""
        tables = self._get_tables(db_name)
        views = self._get_views(db_name)
        stored_procedures = self._get_stored_procedures(db_name)
        
        # Create database index page
        self._create_db_index(db_name, tables, views, stored_procedures)
        
        # Create table pages
        for table in tables:
            columns = self._get_columns(db_name, table['TABLE_SCHEMA'], table['TABLE_NAME'])
            self._create_table_page(db_name, table, columns)
        
        # Create view pages
        for view in views:
            self._create_view_page(db_name, view)
        
        # Create stored procedure pages
        for proc in stored_procedures:
            self._create_procedure_page(db_name, proc)
    
    def _create_db_index(self, db_name: str, tables: List[Dict], views: List[Dict], stored_procedures: List[Dict]):
        """Create the index page for a database"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{db_name} Documentation</title>
            <link rel="stylesheet" href="../css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>{db_name} Database Documentation</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <h2>Tables</h2>
                <ul>
                    {''.join(f'<li><a href="tables/{table["TABLE_SCHEMA"]}.{table["TABLE_NAME"]}.html">{table["TABLE_SCHEMA"]}.{table["TABLE_NAME"]}</a></li>' for table in tables)}
                </ul>
                
                <h2>Views</h2>
                <ul>
                    {''.join(f'<li><a href="views/{view["TABLE_SCHEMA"]}.{view["TABLE_NAME"]}.html">{view["TABLE_SCHEMA"]}.{view["TABLE_NAME"]}</a></li>' for view in views)}
                </ul>
                
                <h2>Stored Procedures</h2>
                <ul>
                    {''.join(f'<li><a href="procedures/{proc["SPECIFIC_SCHEMA"]}.{proc["SPECIFIC_NAME"]}.html">{proc["SPECIFIC_SCHEMA"]}.{proc["SPECIFIC_NAME"]}</a></li>' for proc in stored_procedures)}
                </ul>
            </div>
        </body>
        </html>
        """
        
        os.makedirs(f"public/docs/{db_name}", exist_ok=True)
        with open(f"public/docs/{db_name}/index.html", 'w') as f:
            f.write(html)
    
    def _create_table_page(self, db_name: str, table: Dict, columns: List[Dict]):
        """Create a page for a table"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{table['TABLE_SCHEMA']}.{table['TABLE_NAME']} - {db_name}</title>
            <link rel="stylesheet" href="../../css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>{table['TABLE_SCHEMA']}.{table['TABLE_NAME']}</h1>
                <p>Database: {db_name}</p>
                <p>Type: {table['TABLE_TYPE']}</p>
                {f"<p>Description: {table['DESCRIPTION']}</p>" if table['DESCRIPTION'] else ""}
                
                <h2>Columns</h2>
                <table>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Nullable</th>
                        <th>Default</th>
                        <th>Description</th>
                    </tr>
                    {''.join(f"""
                    <tr>
                        <td>{col['COLUMN_NAME']}</td>
                        <td>{col['DATA_TYPE']}{f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""}</td>
                        <td>{col['IS_NULLABLE']}</td>
                        <td>{col['COLUMN_DEFAULT'] or ""}</td>
                        <td>{col['DESCRIPTION'] or ""}</td>
                    </tr>
                    """ for col in columns)}
                </table>
                
                <p><a href="../index.html">Back to {db_name} Index</a></p>
            </div>
        </body>
        </html>
        """
        
        os.makedirs(f"public/docs/{db_name}/tables", exist_ok=True)
        with open(f"public/docs/{db_name}/tables/{table['TABLE_SCHEMA']}.{table['TABLE_NAME']}.html", 'w') as f:
            f.write(html)
    
    def _create_view_page(self, db_name: str, view: Dict):
        """Create a page for a view"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{view['TABLE_SCHEMA']}.{view['TABLE_NAME']} - {db_name}</title>
            <link rel="stylesheet" href="../../css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>{view['TABLE_SCHEMA']}.{view['TABLE_NAME']}</h1>
                <p>Database: {db_name}</p>
                <p>Type: View</p>
                {f"<p>Description: {view['DESCRIPTION']}</p>" if view['DESCRIPTION'] else ""}
                
                <h2>Definition</h2>
                <pre><code>{view['VIEW_DEFINITION']}</code></pre>
                
                <p><a href="../index.html">Back to {db_name} Index</a></p>
            </div>
        </body>
        </html>
        """
        
        os.makedirs(f"public/docs/{db_name}/views", exist_ok=True)
        with open(f"public/docs/{db_name}/views/{view['TABLE_SCHEMA']}.{view['TABLE_NAME']}.html", 'w') as f:
            f.write(html)
    
    def _create_procedure_page(self, db_name: str, proc: Dict):
        """Create a page for a stored procedure"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{proc['SPECIFIC_SCHEMA']}.{proc['SPECIFIC_NAME']} - {db_name}</title>
            <link rel="stylesheet" href="../../css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>{proc['SPECIFIC_SCHEMA']}.{proc['SPECIFIC_NAME']}</h1>
                <p>Database: {db_name}</p>
                <p>Type: Stored Procedure</p>
                {f"<p>Description: {proc['DESCRIPTION']}</p>" if proc['DESCRIPTION'] else ""}
                
                <h2>Definition</h2>
                <pre><code>{proc['PROCEDURE_DEFINITION']}</code></pre>
                
                <p><a href="../index.html">Back to {db_name} Index</a></p>
            </div>
        </body>
        </html>
        """
        
        os.makedirs(f"public/docs/{db_name}/procedures", exist_ok=True)
        with open(f"public/docs/{db_name}/procedures/{proc['SPECIFIC_SCHEMA']}.{proc['SPECIFIC_NAME']}.html", 'w') as f:
            f.write(html)
    
    def _create_css(self):
        """Create CSS file for documentation"""
        css = """
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #333;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        
        h2 {
            color: #444;
            margin-top: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        
        tr:hover {
            background-color: #f5f5f5;
        }
        
        pre {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        
        code {
            font-family: 'Courier New', Courier, monospace;
            font-size: 14px;
        }
        
        a {
            color: #007bff;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        ul {
            list-style-type: none;
            padding: 0;
        }
        
        li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        
        li:last-child {
            border-bottom: none;
        }
        """
        
        os.makedirs("public/docs/css", exist_ok=True)
        with open("public/docs/css/style.css", 'w') as f:
            f.write(css)
    
    def generate(self):
        """Generate all documentation"""
        try:
            # Create CSS file
            self._create_css()
            
            # Generate documentation for each database
            for db_name in self.config['sql_server']['databases']:
                print(f"Generating documentation for {db_name}...")
                self._generate_html(db_name)
            
            # Create main index page
            self._create_main_index()
            
            print("Documentation generated successfully!")
            
        except Exception as e:
            print(f"Error generating documentation: {e}")
            raise
        finally:
            # Close all database connections
            for conn in self.connections.values():
                conn['connection'].close()
    
    def _create_main_index(self):
        """Create the main index page"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Documentation</title>
            <link rel="stylesheet" href="css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>Database Documentation</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <h2>Databases</h2>
                <ul>
                    {''.join(f'<li><a href="{db}/index.html">{db}</a></li>' for db in self.config['sql_server']['databases'])}
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open("public/docs/index.html", 'w') as f:
            f.write(html)

if __name__ == "__main__":
    generator = DatabaseDocGenerator()
    generator.generate() 