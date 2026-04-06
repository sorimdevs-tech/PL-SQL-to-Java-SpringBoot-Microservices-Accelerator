# PL/SQL → Java Modernization Platform

A comprehensive AI-powered platform for converting legacy PL/SQL code to modern Java Spring Boot applications.

## 🚀 Overview

This platform provides a complete solution for modernizing PL/SQL applications by:

- **Automated Code Conversion**: Convert PL/SQL procedures, functions, triggers, and packages to Java
- **Intelligent Dependency Analysis**: Analyze complex PL/SQL dependencies and relationships
- **Spring Boot Project Generation**: Generate complete, production-ready Spring Boot applications
- **JPA Entity Mapping**: Automatically create JPA entities and repository interfaces
- **Comprehensive Testing**: Generate unit tests and integration tests
- **Advanced Optimizations**: Performance, security, and code quality optimizations
- **Deployment Ready**: Generate Docker, Kubernetes, and CI/CD configurations

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Input Layer   │    │  Processing     │    │  Output Layer   │
│                 │    │  Pipeline       │    │                 │
│ • PL/SQL Files  │───▶│ • Parser        │───▶│ • Java Code     │
│ • Git Repos     │    │ • AST Generator │    │ • Spring Boot   │
│ • Databases     │    │ • Dependency    │    │ • JPA Entities  │
│                 │    │   Analyzer      │    │ • Tests         │
└─────────────────┘    │ • LLM Engine    │    │ • Documentation │
                       │ • Generator     │    │ • Deployment    │
                       │ • Validator     │    │   Configs       │
                       │ • Optimizer     │    └─────────────────┘
                       └─────────────────┘
```

## 📁 Project Structure

```
plsql-modernization-platform/
├── src/
│   ├── utils/              # Utility modules
│   │   ├── config.py       # Configuration management
│   │   ├── logger.py       # Logging utilities
│   │   └── file_utils.py   # File extraction utilities
│   ├── parser/             # PL/SQL parsing
│   │   ├── plsql_parser.py # ANTLR-based parser
│   │   └── sql_extractor.py # SQL extraction and AST generation
│   ├── analyzer/           # Dependency analysis
│   │   └── dependency_graph.py # NetworkX-based dependency analysis
│   ├── converter/          # LLM conversion engine
│   │   └── llm_engine.py   # OpenAI/Anthropic integration
│   ├── generator/          # Code generation
│   │   ├── spring_boot_generator.py # Spring Boot project generator
│   │   └── sql_to_jpa_converter.py # JPA entity and repository generator
│   ├── validator/          # Testing and validation
│   │   └── test_generator.py # Unit and integration test generation
│   └── advanced/           # Advanced features
│       ├── optimization_engine.py # Performance and security optimization
│       └── advanced_features.py # Documentation, deployment, monitoring
├── config.json             # Platform configuration
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Java 17+ (for generated applications)
- Maven or Gradle (for building generated projects)
- Optional: Docker, Kubernetes (for deployment features)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd plsql-modernization-platform
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure LLM providers:**
   Edit `config.json` to add your OpenAI or Anthropic API keys:
   ```json
   {
     "llm": {
       "provider": "openai",
       "api_key": "your-api-key-here",
       "model": "gpt-4"
     }
   }
   ```

## 🚀 Usage

### Basic Usage

Convert a single PL/SQL file:
```bash
python main.py input.sql
```

### Advanced Usage

Convert from Git repository:
```bash
python main.py --source-type git --repo-url https://github.com/example/plsql-repo
```

Convert from database:
```bash
python main.py --source-type database --connection-string "oracle://user:pass@host:port/service"
```

Enable verbose logging:
```bash
python main.py input.sql --verbose
```

Use custom configuration:
```bash
python main.py input.sql --config custom-config.json
```

## 📋 Supported PL/SQL Features

### ✅ Fully Supported
- **Procedures**: Complete conversion with parameter mapping
- **Functions**: Return type mapping and exception handling
- **Triggers**: Event-driven logic conversion to Spring events
- **Packages**: Modular conversion to Java classes
- **SQL Statements**: Complete SQL to JPA repository conversion
- **Data Types**: Comprehensive type mapping (VARCHAR, NUMBER, DATE, etc.)
- **Control Structures**: IF/ELSE, CASE, loops, exception handling

### 🔄 Partially Supported
- **Cursors**: Converted to Spring Data repositories
- **Collections**: Mapped to Java collections
- **Dynamic SQL**: Converted with parameter binding

### ⚠️ Manual Review Required
- **Complex Business Logic**: May need manual refinement
- **Database-Specific Features**: Oracle-specific functions
- **Performance-Critical Code**: May need optimization

## 🎯 Generated Output

### Java Spring Boot Application
- **Controllers**: REST API endpoints with proper annotations
- **Services**: Business logic layer with dependency injection
- **Repositories**: JPA repository interfaces with custom queries
- **Entities**: JPA entity classes with relationships
- **DTOs**: Data transfer objects for API contracts
- **Exceptions**: Custom exception handling
- **Configuration**: Complete Spring Boot configuration

### Project Structure
```
generated-app/
├── src/main/java/com/company/project/
│   ├── Application.java              # Main application class
│   ├── controller/                   # REST controllers
│   ├── service/                      # Business logic services
│   ├── repository/                   # JPA repositories
│   ├── entity/                       # JPA entities
│   ├── dto/                          # Data transfer objects
│   ├── exception/                    # Custom exceptions
│   └── config/                       # Configuration classes
├── src/main/resources/
│   ├── application.yml              # Application configuration
│   └── application.properties       # Alternative configuration
├── src/test/                        # Generated tests
├── pom.xml                          # Maven build file
├── build.gradle                     # Gradle build file
├── Dockerfile                       # Docker configuration
└── README.md                        # Project documentation
```

### Testing and Validation
- **Unit Tests**: JUnit 5 tests for all components
- **Integration Tests**: End-to-end testing with test data
- **Code Quality**: Static analysis and code quality checks
- **Security Analysis**: Vulnerability and security issue detection
- **Performance Analysis**: Bottleneck identification and optimization suggestions

## ⚙️ Configuration

### Main Configuration (`config.json`)

```json
{
  "input": {
    "source_types": ["file", "git", "database"],
    "file_extensions": [".sql", ".pls", ".pkb", ".pks"],
    "max_file_size": "10MB"
  },
  "llm": {
    "provider": "openai",
    "api_key": "your-api-key",
    "model": "gpt-4",
    "temperature": 0.1,
    "max_tokens": 4000,
    "batch_size": 5
  },
  "output": {
    "target_directory": "./output",
    "project_name": "converted-app",
    "package_name": "com.company.project",
    "java_version": "17",
    "spring_boot_version": "3.1.0"
  },
  "validation": {
    "enable_sql_validation": true,
    "enable_security_analysis": true,
    "enable_performance_analysis": true
  },
  "advanced": {
    "documentation_generation": true,
    "api_documentation": true,
    "code_analysis": true,
    "integration_tests": true,
    "deployment_config": true,
    "monitoring_setup": true
  }
}
```

## 🔧 Advanced Features

### 1. Documentation Generation
- **API Documentation**: OpenAPI/Swagger specifications
- **Architecture Documentation**: System architecture and design patterns
- **Deployment Guide**: Step-by-step deployment instructions
- **Postman Collections**: API testing collections

### 2. Code Analysis
- **Quality Metrics**: Code complexity, maintainability, testability
- **Security Analysis**: Vulnerability detection and security best practices
- **Performance Analysis**: Bottleneck identification and optimization suggestions
- **Dependency Analysis**: Dependency graph and circular dependency detection

### 3. Deployment Configuration
- **Docker**: Multi-stage Dockerfiles with optimization
- **Kubernetes**: Complete K8s manifests (Deployments, Services, ConfigMaps)
- **CI/CD**: GitHub Actions and Jenkins pipeline configurations
- **Environment Configs**: Development, staging, and production configurations

### 4. Monitoring and Observability
- **Health Checks**: Spring Boot health check endpoints
- **Metrics**: Prometheus metrics configuration
- **Logging**: Structured logging configuration
- **Tracing**: Distributed tracing setup

## 🧪 Testing

### Generated Test Structure
```
tests/
├── unit/                          # Unit tests
│   ├── entity/                    # Entity tests
│   ├── repository/                # Repository tests
│   ├── service/                   # Service tests
│   └── controller/                # Controller tests
├── integration/                   # Integration tests
│   ├── api/                       # API integration tests
│   └── database/                  # Database integration tests
└── performance/                   # Performance tests
```

### Test Features
- **Mocking**: Mockito-based mocking for dependencies
- **Test Data**: Generated test data and fixtures
- **Assertions**: Comprehensive assertion coverage
- **Test Configuration**: Environment-specific test configurations

## 📊 Performance and Optimization

### Code Optimization Features
- **Dead Code Elimination**: Remove unused imports and code
- **Loop Optimization**: Optimize inefficient loop patterns
- **String Operations**: Replace inefficient string concatenation
- **Collection Optimization**: Use appropriate collection types
- **Memory Management**: Identify and fix memory leaks

### Performance Analysis
- **Complexity Analysis**: Cyclomatic complexity measurement
- **Bottleneck Detection**: Identify performance bottlenecks
- **Memory Usage**: Monitor memory consumption patterns
- **CPU Usage**: Analyze CPU-intensive operations

## 🔒 Security Features

### Security Analysis
- **SQL Injection**: Detect and prevent SQL injection vulnerabilities
- **XSS Prevention**: Cross-site scripting vulnerability detection
- **Authentication Bypass**: Identify authentication vulnerabilities
- **Sensitive Data**: Detect sensitive data exposure

### Security Best Practices
- **Input Validation**: Proper input validation and sanitization
- **Error Handling**: Secure error handling without information leakage
- **Access Control**: Proper authorization and access control
- **Data Encryption**: Sensitive data encryption recommendations

## 🚀 Deployment

### Docker Deployment
```bash
# Build the application
mvn clean package

# Build Docker image
docker build -t plsql-app .

# Run container
docker run -p 8080:8080 plsql-app
```

### Kubernetes Deployment
```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/kubernetes/

# Check deployment status
kubectl get deployments
kubectl get pods
```

### CI/CD Integration
The platform generates complete CI/CD pipelines for:
- **GitHub Actions**: Automated build, test, and deployment
- **Jenkins**: Jenkinsfile for Jenkins pipeline integration
- **GitLab CI**: GitLab CI/CD configuration

## 📈 Migration Metrics

### Conversion Statistics
The platform tracks and reports:
- **Code Coverage**: Percentage of PL/SQL code converted
- **Complexity Metrics**: Before and after complexity analysis
- **Test Coverage**: Generated test coverage percentage
- **Performance Metrics**: Performance improvements and bottlenecks

### Quality Metrics
- **Code Quality Score**: Overall code quality assessment
- **Security Score**: Security vulnerability assessment
- **Maintainability Index**: Code maintainability measurement
- **Technical Debt**: Estimated technical debt

## 🤖 AI-Powered Features

### LLM Integration
- **OpenAI GPT-4**: Primary LLM for code conversion
- **Anthropic Claude**: Alternative LLM option
- **Context Awareness**: Maintains context across large codebases
- **Error Correction**: AI-powered error detection and correction

### Intelligent Analysis
- **Pattern Recognition**: Identify common PL/SQL patterns
- **Best Practices**: Apply Java and Spring Boot best practices
- **Code Suggestions**: AI-powered code improvement suggestions
- **Documentation**: AI-generated code documentation

## 🛠️ Troubleshooting

### Common Issues

#### LLM API Errors
```bash
# Check API key configuration
python -c "import json; print(json.load(open('config.json'))['llm']['api_key'])"

# Verify network connectivity
curl https://api.openai.com/v1/models
```

#### Dependency Issues
```bash
# Reinstall Python dependencies
pip install -r requirements.txt --force-reinstall

# Check Java version
java -version
```

#### File Parsing Errors
```bash
# Check file encoding
file input.sql

# Validate PL/SQL syntax
# (Use your database's PL/SQL validator)
```

### Debug Mode
Enable verbose logging for detailed debugging:
```bash
python main.py input.sql --verbose
```

## 📚 Examples

### Basic Conversion
```bash
# Convert a simple PL/SQL procedure
python main.py examples/simple_procedure.sql

# Output will be in ./output/generated/
```

### Enterprise Conversion
```bash
# Convert from Git repository
python main.py --source-type git --repo-url https://github.com/company/plsql-app

# Generate with advanced features
# (Configure in config.json)
```

### Database Conversion
```bash
# Convert from Oracle database
python main.py --source-type database --connection-string "oracle://user:pass@host:1521/service"
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for your changes
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ANTLR**: For the powerful parser generator
- **NetworkX**: For dependency graph analysis
- **OpenAI/Anthropic**: For LLM capabilities
- **Spring Boot Team**: For the excellent framework
- **All Contributors**: For their valuable contributions

## 📞 Support

For support and questions:
- **GitHub Issues**: [Create an issue](https://github.com/your-org/plsql-modernization/issues)
- **Documentation**: [Read the docs](docs/)
- **Community**: [Join our community](https://discord.gg/your-invite)

## 🔄 Changelog

### v1.0.0 (Current)
- ✅ Complete PL/SQL to Java conversion pipeline
- ✅ Spring Boot project generation
- ✅ JPA entity and repository generation
- ✅ Comprehensive testing and validation
- ✅ Advanced optimization features
- ✅ Deployment configuration generation
- ✅ Documentation and monitoring setup

---

**Note**: This platform is designed for enterprise-scale PL/SQL modernization projects. Always review and test generated code before production deployment.