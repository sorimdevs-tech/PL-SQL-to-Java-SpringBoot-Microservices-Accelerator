"""
Dependency Analyzer for PL/SQL Modernization Platform
Analyzes dependencies between PL/SQL components using NetworkX
"""

import networkx as nx
from typing import Dict, List, Any, Set, Tuple, Optional
from dataclasses import dataclass
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Dependency:
    """Represents a dependency between two components"""
    source: str
    target: str
    type: str  # procedure_call, function_call, table_access, view_access, package_dependency
    line_number: Optional[int] = None
    context: Optional[str] = None


@dataclass
class Component:
    """Represents a PL/SQL component"""
    name: str
    type: str  # procedure, function, trigger, package, table, view
    schema: Optional[str] = None
    dependencies: List[str] = None
    dependents: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.dependents is None:
            self.dependents = []


class DependencyAnalyzer:
    """Analyzes dependencies between PL/SQL components"""
    
    def __init__(self):
        """Initialize dependency analyzer"""
        self.graph = nx.DiGraph()  # Directed graph for dependencies
        self.components: Dict[str, Component] = {}
        self.dependencies: List[Dependency] = []
        
        # Dependency patterns to detect
        self.dependency_patterns = {
            'procedure_call': [
                r'(?i)\b(\w+)\s*\(',
                r'(?i)CALL\s+(\w+)',
                r'(?i)EXECUTE\s+(\w+)',
            ],
            'function_call': [
                r'(?i)SELECT\s+.*?\b(\w+)\s*\(',
                r'(?i)WHERE\s+.*?\b(\w+)\s*\(',
                r'(?i)SET\s+.*?\b(\w+)\s*\(',
            ],
            'table_access': [
                r'(?i)FROM\s+(\w+)',
                r'(?i)INTO\s+(\w+)',
                r'(?i)UPDATE\s+(\w+)',
                r'(?i)DELETE\s+FROM\s+(\w+)',
                r'(?i)JOIN\s+(\w+)',
            ],
            'view_access': [
                r'(?i)FROM\s+(\w+)',
                r'(?i)INTO\s+(\w+)',
            ],
            'package_dependency': [
                r'(?i)\b(\w+)\.\w+',
            ]
        }
    
    def analyze(self, ast_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze dependencies from AST results
        
        Args:
            ast_results (Dict[str, Any]): Parsed AST results
            
        Returns:
            Dict[str, Any]: Dependency analysis results
        """
        logger.info("Starting dependency analysis...")
        
        # Build component graph
        self._build_component_graph(ast_results)
        
        # Analyze dependencies
        dependencies = self._analyze_dependencies(ast_results)
        
        # Generate dependency report
        report = self._generate_dependency_report()
        
        logger.info(f"Dependency analysis completed. Found {len(self.dependencies)} dependencies.")
        
        return {
            'graph': self.graph,
            'components': self.components,
            'dependencies': self.dependencies,
            'report': report
        }
    
    def _build_component_graph(self, ast_results: Dict[str, Any]):
        """Build the component dependency graph"""
        # Add procedures
        for procedure in ast_results.get('procedures', []):
            proc_name = procedure.get('name', 'unknown_procedure')
            self._add_component(proc_name, 'procedure')
            
            # Add dependencies within procedure
            for statement in procedure.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    self._extract_sql_dependencies(proc_name, statement.get('text', ''))
        
        # Add functions
        for function in ast_results.get('functions', []):
            func_name = function.get('name', 'unknown_function')
            self._add_component(func_name, 'function')
            
            # Add dependencies within function
            for statement in function.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    self._extract_sql_dependencies(func_name, statement.get('text', ''))
        
        # Add triggers
        for trigger in ast_results.get('triggers', []):
            trigger_name = trigger.get('name', 'unknown_trigger')
            self._add_component(trigger_name, 'trigger')
            
            # Add dependencies within trigger
            for statement in trigger.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    self._extract_sql_dependencies(trigger_name, statement.get('text', ''))
        
        # Add packages
        for package in ast_results.get('packages', []):
            package_name = package.get('name', 'unknown_package')
            self._add_component(package_name, 'package')
    
    def _add_component(self, name: str, component_type: str, schema: Optional[str] = None):
        """Add a component to the graph"""
        if name not in self.components:
            component = Component(name=name, type=component_type, schema=schema)
            self.components[name] = component
            self.graph.add_node(name, component=component)
    
    def _extract_sql_dependencies(self, source_component: str, sql_statement: str):
        """Extract dependencies from SQL statement"""
        for dep_type, patterns in self.dependency_patterns.items():
            for pattern in patterns:
                matches = self._find_pattern_matches(pattern, sql_statement)
                for match in matches:
                    target = match.strip()
                    if target and target != source_component:
                        # Add dependency
                        dependency = Dependency(
                            source=source_component,
                            target=target,
                            type=dep_type,
                            context=sql_statement
                        )
                        self.dependencies.append(dependency)
                        
                        # Add to graph
                        if target not in self.graph:
                            # Determine component type based on context
                            component_type = self._infer_component_type(target, dep_type)
                            self._add_component(target, component_type)
                        
                        # Add edge to graph
                        if not self.graph.has_edge(source_component, target):
                            self.graph.add_edge(source_component, target, type=dep_type)
    
    def _find_pattern_matches(self, pattern: str, text: str) -> List[str]:
        """Find matches for a pattern in text"""
        import re
        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches
    
    def _infer_component_type(self, name: str, dependency_type: str) -> str:
        """Infer component type based on dependency context"""
        if dependency_type in ['table_access', 'view_access']:
            # Check if it's likely a table or view based on naming conventions
            if name.upper().endswith('_V') or name.upper().endswith('_VIEW'):
                return 'view'
            else:
                return 'table'
        elif dependency_type == 'procedure_call':
            return 'procedure'
        elif dependency_type == 'function_call':
            return 'function'
        elif dependency_type == 'package_dependency':
            return 'package'
        else:
            return 'unknown'
    
    def _analyze_dependencies(self, ast_results: Dict[str, Any]) -> List[Dependency]:
        """Analyze all dependencies"""
        all_dependencies = []
        
        # Analyze procedure dependencies
        for procedure in ast_results.get('procedures', []):
            deps = self._analyze_procedure_dependencies(procedure)
            all_dependencies.extend(deps)
        
        # Analyze function dependencies
        for function in ast_results.get('functions', []):
            deps = self._analyze_function_dependencies(function)
            all_dependencies.extend(deps)
        
        # Analyze trigger dependencies
        for trigger in ast_results.get('triggers', []):
            deps = self._analyze_trigger_dependencies(trigger)
            all_dependencies.extend(deps)
        
        return all_dependencies
    
    def _analyze_procedure_dependencies(self, procedure: Dict[str, Any]) -> List[Dependency]:
        """Analyze dependencies for a single procedure"""
        dependencies = []
        proc_name = procedure.get('name', 'unknown')
        
        # Analyze parameter dependencies
        for param in procedure.get('parameters', []):
            param_type = param.get('type', '')
            if '.' in param_type:  # Package.type
                package_name = param_type.split('.')[0]
                dep = Dependency(
                    source=proc_name,
                    target=package_name,
                    type='package_dependency',
                    context=f"Parameter type: {param_type}"
                )
                dependencies.append(dep)
        
        # Analyze SQL statement dependencies
        for statement in procedure.get('statements', []):
            if statement.get('type') == 'sql_statement':
                sql_text = statement.get('text', '')
                deps = self._extract_statement_dependencies(proc_name, sql_text)
                dependencies.extend(deps)
        
        return dependencies
    
    def _analyze_function_dependencies(self, function: Dict[str, Any]) -> List[Dependency]:
        """Analyze dependencies for a single function"""
        dependencies = []
        func_name = function.get('name', 'unknown')
        
        # Analyze return type dependencies
        return_type = function.get('return_type', '')
        if '.' in return_type:  # Package.type
            package_name = return_type.split('.')[0]
            dep = Dependency(
                source=func_name,
                target=package_name,
                type='package_dependency',
                context=f"Return type: {return_type}"
            )
            dependencies.append(dep)
        
        # Analyze SQL statement dependencies
        for statement in function.get('statements', []):
            if statement.get('type') == 'sql_statement':
                sql_text = statement.get('text', '')
                deps = self._extract_statement_dependencies(func_name, sql_text)
                dependencies.extend(deps)
        
        return dependencies
    
    def _analyze_trigger_dependencies(self, trigger: Dict[str, Any]) -> List[Dependency]:
        """Analyze dependencies for a single trigger"""
        dependencies = []
        trigger_name = trigger.get('name', 'unknown')
        
        # Analyze table dependencies
        table_name = trigger.get('table', '')
        if table_name:
            dep = Dependency(
                source=trigger_name,
                target=table_name,
                type='table_access',
                context=f"Trigger on table: {table_name}"
            )
            dependencies.append(dep)
        
        # Analyze SQL statement dependencies
        for statement in trigger.get('statements', []):
            if statement.get('type') == 'sql_statement':
                sql_text = statement.get('text', '')
                deps = self._extract_statement_dependencies(trigger_name, sql_text)
                dependencies.extend(deps)
        
        return dependencies
    
    def _extract_statement_dependencies(self, source: str, sql_text: str) -> List[Dependency]:
        """Extract dependencies from a single SQL statement"""
        dependencies = []
        
        # Extract table references
        table_deps = self._extract_table_dependencies(source, sql_text)
        dependencies.extend(table_deps)
        
        # Extract procedure/function calls
        call_deps = self._extract_call_dependencies(source, sql_text)
        dependencies.extend(call_deps)
        
        return dependencies
    
    def _extract_table_dependencies(self, source: str, sql_text: str) -> List[Dependency]:
        """Extract table dependencies from SQL text"""
        dependencies = []
        
        # Look for FROM clauses
        from_matches = self._find_pattern_matches(r'(?i)FROM\s+(\w+)', sql_text)
        for table in from_matches:
            dep = Dependency(
                source=source,
                target=table,
                type='table_access',
                context=sql_text
            )
            dependencies.append(dep)
        
        # Look for JOIN clauses
        join_matches = self._find_pattern_matches(r'(?i)JOIN\s+(\w+)', sql_text)
        for table in join_matches:
            dep = Dependency(
                source=source,
                target=table,
                type='table_access',
                context=sql_text
            )
            dependencies.append(dep)
        
        return dependencies
    
    def _extract_call_dependencies(self, source: str, sql_text: str) -> List[Dependency]:
        """Extract procedure/function call dependencies"""
        dependencies = []
        
        # Look for function calls in SELECT
        func_matches = self._find_pattern_matches(r'(?i)SELECT\s+.*?\b(\w+)\s*\(', sql_text)
        for func in func_matches:
            dep = Dependency(
                source=source,
                target=func,
                type='function_call',
                context=sql_text
            )
            dependencies.append(dep)
        
        # Look for procedure calls
        proc_matches = self._find_pattern_matches(r'(?i)\b(\w+)\s*\(', sql_text)
        for proc in proc_matches:
            # Filter out SQL keywords
            if proc.upper() not in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE']:
                dep = Dependency(
                    source=source,
                    target=proc,
                    type='procedure_call',
                    context=sql_text
                )
                dependencies.append(dep)
        
        return dependencies
    
    def _generate_dependency_report(self) -> Dict[str, Any]:
        """Generate comprehensive dependency report"""
        report = {
            'total_components': len(self.components),
            'total_dependencies': len(self.dependencies),
            'dependency_types': {},
            'circular_dependencies': [],
            'orphaned_components': [],
            'highly_connected_components': [],
            'dependency_depth': {}
        }
        
        # Count dependency types
        for dep in self.dependencies:
            dep_type = dep.type
            report['dependency_types'][dep_type] = report['dependency_types'].get(dep_type, 0) + 1
        
        # Find circular dependencies
        try:
            cycles = list(nx.simple_cycles(self.graph))
            report['circular_dependencies'] = cycles
        except nx.NetworkXError:
            pass
        
        # Find orphaned components (no dependencies or dependents)
        for component_name in self.components:
            if not self.graph.in_degree(component_name) and not self.graph.out_degree(component_name):
                report['orphaned_components'].append(component_name)
        
        # Find highly connected components
        for component_name in self.components:
            total_connections = (self.graph.in_degree(component_name) + 
                               self.graph.out_degree(component_name))
            if total_connections > 5:  # Threshold for "highly connected"
                report['highly_connected_components'].append({
                    'component': component_name,
                    'connections': total_connections,
                    'dependents': list(self.graph.predecessors(component_name)),
                    'dependencies': list(self.graph.successors(component_name))
                })
        
        # Calculate dependency depth
        for component_name in self.components:
            try:
                depth = nx.dag_longest_path_length(self.graph, component_name)
                report['dependency_depth'][component_name] = depth
            except nx.NetworkXError:
                # Component is part of a cycle
                report['dependency_depth'][component_name] = -1
        
        return report
    
    def get_component_dependencies(self, component_name: str) -> List[str]:
        """Get all dependencies for a component"""
        if component_name in self.graph:
            return list(self.graph.successors(component_name))
        return []
    
    def get_component_dependents(self, component_name: str) -> List[str]:
        """Get all components that depend on this component"""
        if component_name in self.graph:
            return list(self.graph.predecessors(component_name))
        return []
    
    def get_dependency_path(self, source: str, target: str) -> List[str]:
        """Get dependency path from source to target"""
        try:
            if nx.has_path(self.graph, source, target):
                return nx.shortest_path(self.graph, source, target)
        except nx.NetworkXNoPath:
            pass
        return []
    
    def is_circular_dependency(self, component_name: str) -> bool:
        """Check if a component is part of a circular dependency"""
        try:
            return nx.is_directed_acyclic_graph(self.graph)
        except:
            return False
    
    def get_topological_order(self) -> List[str]:
        """Get topological order of components"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            logger.warning("Graph has cycles, cannot compute topological order")
            return []
    
    def export_graph(self, format: str = 'json', filename: Optional[str] = None) -> str:
        """Export dependency graph to file"""
        if format == 'json':
            import json
            graph_data = nx.node_link_data(self.graph)
            if filename:
                with open(filename, 'w') as f:
                    json.dump(graph_data, f, indent=2)
                logger.info(f"Graph exported to {filename}")
            return json.dumps(graph_data, indent=2)
        elif format == 'dot':
            dot_data = nx.nx_pydot.to_pydot(self.graph)
            if filename:
                dot_data.write(filename)
                logger.info(f"Graph exported to {filename}")
            return dot_data.to_string()
        else:
            raise ValueError(f"Unsupported export format: {format}")


class DependencyValidator:
    """Validates dependency relationships"""
    
    def __init__(self, dependency_analyzer: DependencyAnalyzer):
        """
        Initialize dependency validator
        
        Args:
            dependency_analyzer (DependencyAnalyzer): Dependency analyzer instance
        """
        self.analyzer = dependency_analyzer
    
    def validate_dependencies(self) -> Dict[str, Any]:
        """Validate all dependencies"""
        validation_results = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'suggestions': []
        }
        
        # Check for circular dependencies
        if self.analyzer.report.get('circular_dependencies'):
            validation_results['valid'] = False
            validation_results['issues'].append({
                'type': 'circular_dependency',
                'description': f"Found {len(self.analyzer.report['circular_dependencies'])} circular dependencies",
                'details': self.analyzer.report['circular_dependencies']
            })
        
        # Check for orphaned components
        orphaned = self.analyzer.report.get('orphaned_components', [])
        if orphaned:
            validation_results['warnings'].append({
                'type': 'orphaned_components',
                'description': f"Found {len(orphaned)} orphaned components",
                'components': orphaned
            })
        
        # Check for highly connected components
        highly_connected = self.analyzer.report.get('highly_connected_components', [])
        if highly_connected:
            validation_results['suggestions'].append({
                'type': 'refactoring_opportunity',
                'description': f"Found {len(highly_connected)} highly connected components that may benefit from refactoring",
                'components': [c['component'] for c in highly_connected]
            })
        
        return validation_results


def create_dependency_analyzer() -> DependencyAnalyzer:
    """Create and return a configured dependency analyzer"""
    return DependencyAnalyzer()


def create_dependency_validator(analyzer: DependencyAnalyzer) -> DependencyValidator:
    """Create and return a configured dependency validator"""
    return DependencyValidator(analyzer)