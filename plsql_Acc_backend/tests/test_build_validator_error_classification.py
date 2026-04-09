from src.generator.build_validator import BuildValidator


def test_parse_build_output_classifies_maven_errors():
    validator = BuildValidator(timeout_seconds=1)
    output = """
    [ERROR] C:/tmp/demo/src/main/java/com/example/CustomerService.java:14:22: cannot find symbol: class CustomerRepository
    [ERROR] C:/tmp/demo/src/main/java/com/example/CustomerService.java:18:17: incompatible types: java.lang.String cannot be converted to java.lang.Long
    """

    errors = validator.parse_build_output("maven", output)

    assert len(errors) == 2
    assert errors[0].category == "dependency"
    assert errors[0].build_tool == "maven"
    assert errors[1].category == "type-mismatch"
