import asyncio

from src.generator.spring_boot_generator import SpringBootGenerator


def _build_generator(tmp_path):
    return SpringBootGenerator(
        {
            "project_name": "demo",
            "package_name": "com.example.demo",
            "target_directory": str(tmp_path),
            "build_tool": "gradle",
        }
    )


def _write_java(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_normalize_service_coerces_numeric_args_for_entity_setters(tmp_path):
    generator = _build_generator(tmp_path)

    _write_java(
        generator.package_path / "entity" / "BookEntity.java",
        """
        package com.example.demo.entity;
        import java.math.BigDecimal;
        public class BookEntity {
            private BigDecimal debycost;
            private BigDecimal lostcost;
            public void setDebycost(BigDecimal debycost) { this.debycost = debycost; }
            public void setLostcost(BigDecimal lostcost) { this.lostcost = lostcost; }
        }
        """,
    )

    service_code = """
    package com.example.demo.service;

    import org.springframework.stereotype.Service;
    import com.example.demo.entity.BookEntity;

    @Service
    public class AddbookLibraryService {
        public void addbook(Long auxdebycost, Long auxlostcost) {
            BookEntity bookEntityTarget = new BookEntity();
            bookEntityTarget.setDebycost(auxdebycost);
            bookEntityTarget.setLostcost(auxlostcost);
        }
    }
    """

    normalized = generator._normalize_service_code("AddbookLibraryService.java", service_code)

    assert "bookEntityTarget.setDebycost((auxdebycost == null ? null : BigDecimal.valueOf(auxdebycost)));" in normalized
    assert "bookEntityTarget.setLostcost((auxlostcost == null ? null : BigDecimal.valueOf(auxlostcost)));" in normalized
    assert "import java.math.BigDecimal;" in normalized


def test_normalize_service_coerces_repository_lookup_args_to_signature_types(tmp_path):
    generator = _build_generator(tmp_path)

    _write_java(
        generator.package_path / "entity" / "CustomerEntity.java",
        """
        package com.example.demo.entity;
        public class CustomerEntity {
            private String username;
            public String getUsername() { return username; }
        }
        """,
    )
    _write_java(
        generator.package_path / "repository" / "CustomerRepository.java",
        """
        package com.example.demo.repository;
        import com.example.demo.entity.CustomerEntity;
        import java.util.Optional;
        import org.springframework.data.jpa.repository.JpaRepository;
        public interface CustomerRepository extends JpaRepository<CustomerEntity, Long> {
            Optional<CustomerEntity> findByUsername(String username);
        }
        """,
    )

    service_code = """
    package com.example.demo.service;

    import java.util.Optional;
    import org.springframework.beans.factory.annotation.Autowired;
    import org.springframework.stereotype.Service;
    import com.example.demo.entity.CustomerEntity;
    import com.example.demo.repository.CustomerRepository;

    @Service
    public class LogincustomerLibraryService {
        @Autowired
        private CustomerRepository customerRepository;

        public void logincustomer(Long username) {
            Optional<CustomerEntity> found = customerRepository.findByUsername(username);
        }
    }
    """

    normalized = generator._normalize_service_code("LogincustomerLibraryService.java", service_code)

    assert "customerRepository.findByUsername((username == null ? null : String.valueOf(username)));" in normalized


def test_normalize_service_coerces_args_using_param_annotated_repository_signatures(tmp_path):
    generator = _build_generator(tmp_path)

    _write_java(
        generator.package_path / "repository" / "OrdersRepository.java",
        """
        package com.example.demo.repository;
        import java.math.BigDecimal;
        import org.springframework.data.jpa.repository.Query;
        import org.springframework.data.jpa.repository.Modifying;
        import org.springframework.data.repository.query.Param;
        import org.springframework.transaction.annotation.Transactional;
        public interface OrdersRepository {
            @Modifying
            @Transactional
            @Query(value = "INSERT INTO orders(amount, status) VALUES (:amount, :status)", nativeQuery = true)
            int insertOrder(@Param("amount") BigDecimal amount, @Param("status") String status);
        }
        """,
    )

    service_code = """
    package com.example.demo.service;

    import org.springframework.beans.factory.annotation.Autowired;
    import org.springframework.stereotype.Service;
    import com.example.demo.repository.OrdersRepository;

    @Service
    public class AddorderLibraryService {
        @Autowired
        private OrdersRepository ordersRepository;

        public void addorder(Long amount, Long status) {
            ordersRepository.insertOrder(amount, status);
        }
    }
    """

    normalized = generator._normalize_service_code("AddorderLibraryService.java", service_code)

    assert "ordersRepository.insertOrder((amount == null ? null : BigDecimal.valueOf(amount)), (status == null ? null : String.valueOf(status)));" in normalized


def test_generate_project_write_path_normalizes_service_types(tmp_path):
    generator = _build_generator(tmp_path)

    java_code = {
        "BookEntity.java": """
            package com.example.demo.entity;
            import java.math.BigDecimal;
            public class BookEntity {
                private BigDecimal debycost;
                public void setDebycost(BigDecimal debycost) { this.debycost = debycost; }
            }
        """,
        "AddbookLibraryService.java": """
            package com.example.demo.service;
            import org.springframework.stereotype.Service;
            import com.example.demo.entity.BookEntity;
            @Service
            public class AddbookLibraryService {
                public void addbook(Long auxdebycost) {
                    BookEntity bookEntityTarget = new BookEntity();
                    bookEntityTarget.setDebycost(auxdebycost);
                }
            }
        """,
    }

    result = asyncio.run(generator.generate_project(java_code, auto_generate_controllers=False))
    service_path = result["java_files"]["AddbookLibraryService.java"]
    written = open(service_path, encoding="utf-8").read()

    assert "bookEntityTarget.setDebycost((auxdebycost == null ? null : BigDecimal.valueOf(auxdebycost)));" in written


def test_normalize_service_imports_optional_for_optional_dot_usage(tmp_path):
    generator = _build_generator(tmp_path)
    service_code = """
    package com.example.demo.service;
    import org.springframework.stereotype.Service;

    @Service
    public class OptionalUsageService {
        public String wrap(String value) {
            return Optional.ofNullable(value).orElse("");
        }
    }
    """

    normalized = generator._normalize_service_code("OptionalUsageService.java", service_code)
    assert "import java.util.Optional;" in normalized


def test_normalize_service_imports_transaction_template_for_bare_usage(tmp_path):
    generator = _build_generator(tmp_path)
    service_code = """
    package com.example.demo.service;
    import org.springframework.stereotype.Service;

    @Service
    public class BatchUsageService {
        private final TransactionTemplate batchTransactionTemplate;

        public BatchUsageService() {
            this.batchTransactionTemplate = null;
        }
    }
    """

    normalized = generator._normalize_service_code("BatchUsageService.java", service_code)
    assert "import org.springframework.transaction.support.TransactionTemplate;" in normalized


def test_normalize_service_imports_platform_transaction_manager_when_used(tmp_path):
    generator = _build_generator(tmp_path)
    service_code = """
    package com.example.demo.service;
    import org.springframework.stereotype.Service;

    @Service
    public class BatchUsageService {
        private final TransactionTemplate batchTransactionTemplate;

        public BatchUsageService(PlatformTransactionManager transactionManager) {
            this.batchTransactionTemplate = new TransactionTemplate(transactionManager);
        }
    }
    """

    normalized = generator._normalize_service_code("BatchUsageService.java", service_code)
    assert "import org.springframework.transaction.support.TransactionTemplate;" in normalized
    assert "import org.springframework.transaction.PlatformTransactionManager;" in normalized


def test_generate_project_write_path_keeps_batch_transaction_imports(tmp_path):
    generator = _build_generator(tmp_path)
    java_code = {
        "BatchUsageService.java": """
            package com.example.demo.service;
            import org.springframework.stereotype.Service;
            @Service
            public class BatchUsageService {
                private final TransactionTemplate batchTransactionTemplate;
                public BatchUsageService(PlatformTransactionManager transactionManager) {
                    this.batchTransactionTemplate = new TransactionTemplate(transactionManager);
                }
            }
        """
    }

    result = asyncio.run(generator.generate_project(java_code, auto_generate_controllers=False))
    service_path = result["java_files"]["BatchUsageService.java"]
    written = open(service_path, encoding="utf-8").read()

    assert "import org.springframework.transaction.support.TransactionTemplate;" in written
    assert "import org.springframework.transaction.PlatformTransactionManager;" in written


def test_generate_method_from_procedure_uses_semantic_batch_reconciliation_template(tmp_path):
    generator = _build_generator(tmp_path)

    source_unit = {
        "name": "reconcile_customer_balances",
        "input_parameters": [
            {"name": "p_batch_size", "type": "NUMBER"},
            {"name": "p_run_mode", "type": "VARCHAR2"},
        ],
        "driving_table": "CUSTOMERS",
        "operations_by_table": {
            "CUSTOMERS": ["SELECT"],
            "ORDERS": ["SELECT"],
            "PAYMENTS": ["SELECT"],
            "CUSTOMER_BALANCE": ["MERGE"],
            "BALANCE_AUDIT_LOG": ["INSERT"],
            "ERROR_LOG": ["INSERT"],
        },
        "lookup_keys": {
            "CUSTOMER_BALANCE": ["CUSTOMER_ID"],
        },
        "bulk_operations": [{"type": "BULK_COLLECT"}],
        "cursor": {"locking": "FOR UPDATE SKIP LOCKED"},
        "transaction": {"has_savepoint": True},
        "semantic_analysis": {
            "process_classification": {"process_type": "batch_reconciliation"},
            "aggregation": {
                "columns": ["orders.amount", "payments.amount"],
            },
        },
    }

    method = generator._generate_method_from_procedure(
        {
            "procedure_name": "reconcile_customer_balances",
            "body": "CREATE OR REPLACE PROCEDURE reconcile_customer_balances IS BEGIN NULL; END;",
            "logic": object(),
            "source_unit": source_unit,
        }
    )

    assert 'Page<CustomersEntity> customerPage = customersRepository.findPageForUpdateSkipLocked(pageRequest);' in method
    assert 'BigDecimal totalOrders = ordersRepository.sumByCustomerId(customer.getCustomerId());' in method
    assert 'Optional<CustomerBalanceEntity> existingBalance = customerBalanceRepository.findByCustomerId(customer.getCustomerId());' in method
    assert 'if (existingBalance.isPresent()) {' in method
    assert '} else {' in method
    assert 'audit.setActionDate(LocalDateTime.now());' in method
    assert 'saveErrorRecord("Unexpected error: " + safeMessage(e));' in method
    assert 'if ("FULL".equalsIgnoreCase(runMode) && !batchHasError) {' in method
    assert 'continue;' in method
