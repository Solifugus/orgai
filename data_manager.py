import yaml
import httpx
import pyodbc
from typing import Dict, List, Optional, Tuple
import os
from datetime import datetime
import json
import glob
import re
from difflib import SequenceMatcher

class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass

class ConnectionError(DatabaseError):
    """Exception raised for database connection errors."""
    pass

class QueryError(DatabaseError):
    """Exception raised for database query errors."""
    pass

class DataManager:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the data manager with configuration."""
        self.config = self._load_config(config_path)
        self.policy_docs = {}
        self.db_connections = {}
        self.documentation = {}

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")

    async def _initialize_data_sources(self):
        """Initialize all data sources based on configuration."""
        policy_config = self.config.get('policy_documents', {})
        enabled = policy_config.get('enabled')
        if enabled in (True, 'true', 'True', '1'):  # More flexible check
            await self._load_policy_documents()
        else:
            print("Policy documents integration disabled")
            self.policy_docs = {}

        if self.config.get('sql_server', {}).get('enabled') is True:
            self._initialize_database_connections()
        else:
            print("Database integration disabled")
            self.db_connections = {}

        if self.config.get('documentation', {}).get('enabled') is True:
            self._load_documentation()
        else:
            print("Local documentation integration disabled")
            self.documentation = {}

    async def _load_policy_documents(self):
        """Load policy documents from the configured source with daily caching."""
        try:
            source = self.config['policy_documents']['source']
            last_update = self.config['policy_documents'].get('last_update')
            
            # Check if we need to update from URL
            should_update = False
            if source.startswith(('http://', 'https://')):
                if not last_update:
                    should_update = True
                else:
                    last_update_time = datetime.fromisoformat(last_update)
                    time_since_update = datetime.now() - last_update_time
                    if time_since_update.days >= 1:
                        should_update = True
            
            if should_update:
                print(f"Updating policy documents from URL: {source}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(source)
                    if response.status_code == 200:
                        self.policy_docs = response.json()
                        # Save to local file
                        with open('policies.json', 'w') as f:
                            json.dump(self.policy_docs, f)
                        self.config['policy_documents']['last_update'] = datetime.now().isoformat()
                        print(f"Successfully updated {len(self.policy_docs)} policy documents")
                    else:
                        raise ConnectionError(f"Failed to load policy documents: HTTP {response.status_code}")
            else:
                # Load from local file
                local_file = 'policies.json'
                if not os.path.exists(local_file):
                    raise FileNotFoundError(f"Policy documents file not found: {local_file}")
                with open(local_file, 'r') as f:
                    self.policy_docs = json.load(f)
                print(f"Using cached policy documents from {local_file} (last updated: {last_update})")
            
        except httpx.RequestError as e:
            raise ConnectionError(f"Network error loading policy documents: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in policy documents: {e}")
        except Exception as e:
            raise ConnectionError(f"Error loading policy documents: {e}")

    def _initialize_database_connections(self):
        """Initialize database connections for each configured database."""
        base_connection_string = self.config['sql_server']['connection_string']
        excluded_schemas = self.config['sql_server']['excluded_schemas']
        
        for db in self.config['sql_server']['databases']:
            try:
                # Add database name to connection string
                conn_str = f"{base_connection_string};DATABASE={db['name']}"
                try:
                    conn = pyodbc.connect(conn_str, timeout=30)  # Add timeout
                    self.db_connections[db['name']] = {
                        'connection': conn,
                        'excluded_schemas': excluded_schemas,
                        'last_refresh': None,
                        'schema_cache': None
                    }
                except pyodbc.Error as e:
                    if "Can't open lib 'ODBC Driver 17 for SQL Server'" in str(e):
                        print(f"Warning: SQL Server ODBC driver not found. Database integration will be disabled.")
                        self.db_connections[db['name']] = {
                            'connection': None,
                            'excluded_schemas': excluded_schemas,
                            'last_refresh': None,
                            'schema_cache': None,
                            'mock_data': True  # Flag to indicate we're using mock data
                        }
                    else:
                        raise
            except Exception as e:
                print(f"Warning: Could not initialize database connection for {db['name']}: {e}")
                self.db_connections[db['name']] = {
                    'connection': None,
                    'excluded_schemas': excluded_schemas,
                    'last_refresh': None,
                    'schema_cache': None,
                    'mock_data': True
                }

    def _load_documentation(self):
        """Load documentation from the configured directory."""
        docs_dir = self.config['documentation']['indexables_dir']
        file_types = self.config['documentation']['file_types']
        excluded_dirs = self.config['documentation']['excluded_dirs']

        if not os.path.exists(docs_dir):
            raise ValueError(f"Documentation directory not found: {docs_dir}")

        for file_type in file_types:
            pattern = os.path.join(docs_dir, f"**/*{file_type}")
            for file_path in glob.glob(pattern, recursive=True):
                if not any(excluded in file_path for excluded in excluded_dirs):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            self.documentation[file_path] = content
                    except UnicodeDecodeError:
                        print(f"Warning: Could not decode file {file_path} as UTF-8")
                    except Exception as e:
                        print(f"Error loading documentation {file_path}: {e}")

        self.config['documentation']['last_update'] = datetime.now().isoformat()

    def _similarity_ratio(self, a: str, b: str) -> float:
        """Calculate string similarity ratio using SequenceMatcher."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _should_refresh_schema(self, db_name: str) -> bool:
        """Determine if database schema should be refreshed."""
        if db_name not in self.db_connections:
            return False
        
        db_info = self.db_connections[db_name]
        if db_info['last_refresh'] is None:
            return True
        
        # Refresh if more than 1 hour has passed
        last_refresh = datetime.fromisoformat(db_info['last_refresh'])
        return (datetime.now() - last_refresh).total_seconds() > 3600

    def get_database_objects(self, db_name: str) -> Dict:
        """Get all database objects (tables, views, stored procedures) for a database."""
        if db_name not in self.db_connections:
            raise ValueError(f"Database {db_name} not found")

        # Check if we're using mock data
        if self.db_connections[db_name].get('mock_data'):
            # Return mock database schema
            return {
                'tables': {
                    'Employees': {
                        'schema': 'dbo',
                        'columns': [
                            {'name': 'EmployeeID', 'type': 'int', 'nullable': 'NO', 'default': None, 'description': 'Primary key', 'position': 1},
                            {'name': 'FirstName', 'type': 'varchar', 'nullable': 'NO', 'default': None, 'description': 'Employee first name', 'position': 2},
                            {'name': 'LastName', 'type': 'varchar', 'nullable': 'NO', 'default': None, 'description': 'Employee last name', 'position': 3},
                            {'name': 'Department', 'type': 'varchar', 'nullable': 'YES', 'default': None, 'description': 'Employee department', 'position': 4}
                        ]
                    },
                    'Departments': {
                        'schema': 'dbo',
                        'columns': [
                            {'name': 'DepartmentID', 'type': 'int', 'nullable': 'NO', 'default': None, 'description': 'Primary key', 'position': 1},
                            {'name': 'DepartmentName', 'type': 'varchar', 'nullable': 'NO', 'default': None, 'description': 'Department name', 'position': 2},
                            {'name': 'ManagerID', 'type': 'int', 'nullable': 'YES', 'default': None, 'description': 'Department manager', 'position': 3}
                        ]
                    }
                },
                'views': {
                    'EmployeeDetails': {
                        'schema': 'dbo',
                        'columns': [
                            {'name': 'EmployeeID', 'type': 'int', 'nullable': 'NO', 'default': None, 'description': 'Employee ID', 'position': 1},
                            {'name': 'FullName', 'type': 'varchar', 'nullable': 'NO', 'default': None, 'description': 'Employee full name', 'position': 2},
                            {'name': 'DepartmentName', 'type': 'varchar', 'nullable': 'YES', 'default': None, 'description': 'Department name', 'position': 3}
                        ]
                    }
                },
                'stored_procedures': {
                    'GetEmployeeByID': {
                        'schema': 'dbo',
                        'definition': 'CREATE PROCEDURE GetEmployeeByID @EmployeeID int AS SELECT * FROM Employees WHERE EmployeeID = @EmployeeID',
                        'comment': 'Retrieves employee information by ID',
                        'created': '2024-01-01',
                        'last_altered': '2024-01-01'
                    }
                },
                'last_refresh': datetime.now().isoformat()
            }

        # Check if we need to refresh the schema
        if not self._should_refresh_schema(db_name):
            return self.db_connections[db_name]['schema_cache']

        db_info = self.db_connections[db_name]
        conn = db_info['connection']
        excluded_schemas = db_info['excluded_schemas']
        cursor = conn.cursor()

        try:
            # Get tables and views with improved query
            cursor.execute("""
                SELECT 
                    t.TABLE_SCHEMA,
                    t.TABLE_NAME,
                    t.TABLE_TYPE,
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.IS_NULLABLE,
                    c.COLUMN_DEFAULT,
                    c.COLUMN_DESCRIPTION,
                    c.ORDINAL_POSITION
                FROM INFORMATION_SCHEMA.TABLES t
                LEFT JOIN INFORMATION_SCHEMA.COLUMNS c 
                    ON t.TABLE_NAME = c.TABLE_NAME 
                    AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
                WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                AND t.TABLE_SCHEMA NOT IN ({})
                ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
            """.format(','.join(['?' for _ in excluded_schemas])), excluded_schemas)

            # Get stored procedures with improved query
            cursor.execute("""
                SELECT 
                    ROUTINE_SCHEMA,
                    ROUTINE_NAME,
                    ROUTINE_TYPE,
                    ROUTINE_DEFINITION,
                    ROUTINE_COMMENT,
                    CREATED,
                    LAST_ALTERED
                FROM INFORMATION_SCHEMA.ROUTINES
                WHERE ROUTINE_TYPE = 'PROCEDURE'
                AND ROUTINE_SCHEMA NOT IN ({})
                ORDER BY ROUTINE_NAME
            """.format(','.join(['?' for _ in excluded_schemas])), excluded_schemas)

            # Process results
            tables = {}
            views = {}
            stored_procs = {}

            # Process tables and views
            for row in cursor.fetchall():
                schema, table_name, table_type, col_name, data_type, nullable, default, description, position = row
                if table_type == 'BASE TABLE':
                    if table_name not in tables:
                        tables[table_name] = {'schema': schema, 'columns': []}
                    if col_name:  # Some rows might be NULL for columns
                        tables[table_name]['columns'].append({
                            'name': col_name,
                            'type': data_type,
                            'nullable': nullable,
                            'default': default,
                            'description': description,
                            'position': position
                        })
                elif table_type == 'VIEW':
                    if table_name not in views:
                        views[table_name] = {'schema': schema, 'columns': []}
                    if col_name:
                        views[table_name]['columns'].append({
                            'name': col_name,
                            'type': data_type,
                            'nullable': nullable,
                            'default': default,
                            'description': description,
                            'position': position
                        })

            # Process stored procedures
            for row in cursor.fetchall():
                schema, name, type, definition, comment, created, last_altered = row
                stored_procs[name] = {
                    'schema': schema,
                    'definition': definition,
                    'comment': comment,
                    'created': created,
                    'last_altered': last_altered
                }

            result = {
                'tables': tables,
                'views': views,
                'stored_procedures': stored_procs,
                'last_refresh': datetime.now().isoformat()
            }

            # Cache the result
            self.db_connections[db_name]['schema_cache'] = result
            self.db_connections[db_name]['last_refresh'] = result['last_refresh']

            return result

        except pyodbc.Error as e:
            raise QueryError(f"Database query error in {db_name}: {e}")
        except Exception as e:
            raise QueryError(f"Unexpected error processing database {db_name}: {e}")

    def search_policy_documents(self, query: str) -> List[Dict]:
        """Search policy documents for relevant information."""
        if not self.config.get('policy_documents', {}).get('enabled', True):
            return []
            
        results = []
        query_terms = query.lower().split()
        
        for doc in self.policy_docs:
            # Get all relevant text fields for searching
            text_fields = [
                doc.get('name', ''),
                doc.get('category_name', ''),
                doc.get('author_name', ''),
                doc.get('applicability_group_name', ''),
                doc.get('text_preview', '')
            ]
            
            # Calculate relevance scores for each field
            name_score = max(self._similarity_ratio(term, doc.get('name', '').lower()) for term in query_terms)
            category_score = max(self._similarity_ratio(term, doc.get('category_name', '').lower()) for term in query_terms)
            author_score = max(self._similarity_ratio(term, doc.get('author_name', '').lower()) for term in query_terms)
            group_score = max(self._similarity_ratio(term, doc.get('applicability_group_name', '').lower()) for term in query_terms)
            preview_score = max(self._similarity_ratio(term, doc.get('text_preview', '').lower()) for term in query_terms)
            
            # Weighted scoring system
            relevance_score = (
                name_score * 0.4 +          # Policy name is most important
                category_score * 0.2 +       # Category is second most important
                preview_score * 0.2 +        # Preview text is third most important
                group_score * 0.1 +          # Applicability group is less important
                author_score * 0.1           # Author is least important
            )
            
            if relevance_score > 0.3:  # Threshold for relevance
                results.append({
                    'name': doc.get('name'),
                    'id': doc.get('id'),
                    'category': doc.get('category_name'),
                    'author': doc.get('author_name'),
                    'applicability_group': doc.get('applicability_group_name'),
                    'preview': doc.get('text_preview'),
                    'urls': {
                        'direct': doc.get('policystat_url_direct'),
                        'latest': doc.get('policystat_url_latest'),
                        'guest_access': doc.get('policystat_url_guest_access')
                    },
                    'relevance_score': relevance_score
                })
        
        # Sort by relevance score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results

    def search_documentation(self, query: str) -> List[Dict]:
        """Search local documentation for relevant information."""
        if not self.config.get('documentation', {}).get('enabled', True):
            return []
            
        results = []
        query_terms = query.lower().split()
        
        for file_path, content in self.documentation.items():
            file_name = os.path.basename(file_path).lower()
            content_lower = content.lower()
            
            # Calculate relevance score
            name_score = max(self._similarity_ratio(term, file_name) for term in query_terms)
            content_score = max(self._similarity_ratio(term, content_lower) for term in query_terms)
            relevance_score = (name_score * 0.4) + (content_score * 0.6)
            
            if relevance_score > 0.3:  # Threshold for relevance
                # Get context around the best match
                lines = content.split('\n')
                best_match_line = 0
                best_match_score = 0
                
                for i, line in enumerate(lines):
                    line_score = max(self._similarity_ratio(term, line.lower()) for term in query_terms)
                    if line_score > best_match_score:
                        best_match_score = line_score
                        best_match_line = i
                
                start = max(0, best_match_line - 2)
                end = min(len(lines), best_match_line + 3)
                context = '\n'.join(lines[start:end])
                
                results.append({
                    'file': file_path,
                    'context': context,
                    'relevance_score': relevance_score
                })
        
        # Sort by relevance score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results

    def get_relevant_database_info(self, query: str) -> List[Dict]:
        """Get relevant database information based on the query."""
        if not self.config.get('sql_server', {}).get('enabled', True):
            return []
            
        results = []
        query_terms = query.lower().split()
        
        for db in self.config['sql_server']['databases']:
            db_name = db['name']
            try:
                db_objects = self.get_database_objects(db_name)
                
                # Search through tables
                for table_name, table_info in db_objects['tables'].items():
                    table_score = max(self._similarity_ratio(term, table_name.lower()) for term in query_terms)
                    if table_score > 0.3:  # Threshold for relevance
                        results.append({
                            'database': db_name,
                            'type': 'table',
                            'schema': table_info['schema'],
                            'name': table_name,
                            'columns': table_info['columns'],
                            'relevance_score': table_score
                        })
                    
                    # Search through columns
                    for column in table_info['columns']:
                        col_score = max(self._similarity_ratio(term, column['name'].lower()) for term in query_terms)
                        if col_score > 0.3:
                            results.append({
                                'database': db_name,
                                'type': 'column',
                                'schema': table_info['schema'],
                                'table': table_name,
                                'column': column,
                                'relevance_score': col_score
                            })

                # Search through views
                for view_name, view_info in db_objects['views'].items():
                    view_score = max(self._similarity_ratio(term, view_name.lower()) for term in query_terms)
                    if view_score > 0.3:
                        results.append({
                            'database': db_name,
                            'type': 'view',
                            'schema': view_info['schema'],
                            'name': view_name,
                            'columns': view_info['columns'],
                            'relevance_score': view_score
                        })

                # Search through stored procedures
                for proc_name, proc_info in db_objects['stored_procedures'].items():
                    proc_score = max(self._similarity_ratio(term, proc_name.lower()) for term in query_terms)
                    if proc_score > 0.3:
                        results.append({
                            'database': db_name,
                            'type': 'stored_procedure',
                            'schema': proc_info['schema'],
                            'name': proc_name,
                            'definition': proc_info['definition'],
                            'relevance_score': proc_score
                        })
            except Exception as e:
                print(f"Error searching database {db_name}: {e}")
        
        # Sort by relevance score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results

    def format_context_for_prompt(self, query: str) -> str:
        """Format relevant context from all sources for the prompt."""
        context_parts = []

        # Add policy document context
        policy_results = self.search_policy_documents(query)
        if policy_results:
            context_parts.append("Relevant Policy Documents:")
            for result in policy_results[:3]:  # Limit to top 3 most relevant
                context_parts.append(f"- {result['name']}")
                context_parts.append(f"  Category: {result['category']}")
                context_parts.append(f"  Author: {result['author']}")
                context_parts.append(f"  Applicability: {result['applicability_group']}")
                context_parts.append(f"  Preview: {result['preview']}")
                if result['urls']['direct']:
                    context_parts.append(f"  URL: {result['urls']['direct']}")

        # Add database context
        db_results = self.get_relevant_database_info(query)
        if db_results:
            context_parts.append("\nRelevant Database Information:")
            for result in db_results[:5]:  # Limit to top 5 most relevant
                if result['type'] == 'table':
                    context_parts.append(f"- Database: {result['database']}")
                    context_parts.append(f"  Table: {result['schema']}.{result['name']}")
                    context_parts.append("  Columns:")
                    for col in result['columns']:
                        desc = f" ({col['description']})" if col.get('description') else ""
                        context_parts.append(f"    - {col['name']}: {col['type']}{desc}")
                elif result['type'] == 'view':
                    context_parts.append(f"- Database: {result['database']}")
                    context_parts.append(f"  View: {result['schema']}.{result['name']}")
                    context_parts.append("  Columns:")
                    for col in result['columns']:
                        desc = f" ({col['description']})" if col.get('description') else ""
                        context_parts.append(f"    - {col['name']}: {col['type']}{desc}")
                elif result['type'] == 'stored_procedure':
                    context_parts.append(f"- Database: {result['database']}")
                    context_parts.append(f"  Stored Procedure: {result['schema']}.{result['name']}")
                    if result.get('comment'):
                        context_parts.append(f"  Description: {result['comment']}")
                    context_parts.append(f"  Definition: {result['definition'][:200]}...")

        # Add documentation context
        doc_results = self.search_documentation(query)
        if doc_results:
            context_parts.append("\nRelevant Documentation:")
            for result in doc_results[:3]:  # Limit to top 3 most relevant
                context_parts.append(f"- File: {result['file']}")
                context_parts.append(f"  Context: {result['context']}")

        return "\n".join(context_parts)

    def close(self):
        """Close all database connections."""
        for db_info in self.db_connections.values():
            try:
                db_info['connection'].close()
            except Exception as e:
                print(f"Error closing database connection: {e}") 