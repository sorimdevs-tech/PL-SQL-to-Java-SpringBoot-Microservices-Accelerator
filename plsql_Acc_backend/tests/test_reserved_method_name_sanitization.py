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


def test_normalize_service_renames_reserved_assert_method(tmp_path):
    generator = _build_generator(tmp_path)
    service_code = """
    package com.example.demo.service;
    import org.springframework.stereotype.Service;

    @Service
    public class AssertLibraryService {
        public void assert(String mode) {
            assert(mode);
        }
    }
    """

    normalized = generator._normalize_service_code("AssertLibraryService.java", service_code)

    assert "public void assertService(String mode)" in normalized
    assert "assertService(mode);" in normalized
    assert "public void assert(" not in normalized


def test_normalize_controller_renames_reserved_assert_method(tmp_path):
    generator = _build_generator(tmp_path)
    controller_code = """
    package com.example.demo.controller;
    import org.springframework.http.ResponseEntity;
    import org.springframework.web.bind.annotation.*;

    @RestController
    public class AssertController {
        @PostMapping
        public ResponseEntity<?> assert(@RequestBody Object payload) {
            return ResponseEntity.ok().build();
        }
    }
    """

    normalized = generator._normalize_controller_code("AssertController.java", controller_code)

    assert "public ResponseEntity<?> assertMethod(@RequestBody Object payload)" in normalized
    assert "public ResponseEntity<?> assert(@RequestBody Object payload)" not in normalized


def test_normalize_controller_rewrites_reserved_service_method_invocation(tmp_path):
    generator = _build_generator(tmp_path)
    controller_code = """
    package com.example.demo.controller;
    import org.springframework.beans.factory.annotation.Autowired;
    import org.springframework.http.ResponseEntity;
    import org.springframework.web.bind.annotation.*;

    @RestController
    public class LoginController {
        @Autowired
        private LoginService loginService;

        @PostMapping("/run")
        public ResponseEntity<?> run(@RequestBody Object request) {
            loginService.assert(request);
            return ResponseEntity.ok().build();
        }
    }
    """

    normalized = generator._normalize_controller_code("LoginController.java", controller_code)

    assert "loginService.assertService(request);" in normalized
    assert "loginService.assert(request);" not in normalized
