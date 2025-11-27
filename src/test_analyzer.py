import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum
import json
import xml.etree.ElementTree as ET

class TestType(Enum):
    PYTEST = "pytest"
    UNITTEST = "unittest"
    NOSE = "nose"
    DJANGO = "django"
    FASTAPI = "fastapi"
    FLASK = "flask"
    STARLETTE = "starlette"

    JEST = "jest"
    MOCHA = "mocha"
    JASMINE = "jasmine"
    CYPRESS = "cypress"
    PLAYWRIGHT = "playwright"
    VITEST = "vitest"

    JUNIT = "junit"
    TESTNG = "testng"
    SPOCK = "spock"
    MAVEN_SUREFIRE = "maven_surefire"

    GO_TEST = "go_test"
    GOCHECK = "gocheck"
    TESTIFY = "testify"

    GOOGLE_TEST = "google_test"
    CATCH2 = "catch2"
    BOOST_TEST = "boost_test"
    CPPUNIT = "cppunit"

    NUNIT = "nunit"
    XUNIT = "xunit"
    MSTEST = "mstest"

    PHPUNIT = "phpunit"

    RSPEC = "rspec"
    MINITEST = "minitest"
    
    UNKNOWN = "unknown"

class ProjectInfo:
    """Информация о найденном проекте"""
    def __init__(self, path: Path, name: str, language: str, confidence: float = 1.0):
        self.path = path
        self.name = name
        self.language = language
        self.confidence = confidence

class TestFramework:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.test_files = []
        self.projects = []
        
    def discover_projects(self) -> List[ProjectInfo]:
        """Находит все проекты в базовой директории"""
        projects = []
        
        for item in self.base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                project_info = self._analyze_project_candidate(item)
                if project_info:
                    projects.append(project_info)

        projects.sort(key=lambda x: x.confidence, reverse=True)
        self.projects = projects
        return projects

    def _analyze_project_candidate(self, candidate_path: Path) -> Optional[ProjectInfo]:
        """Анализирует кандидата на проект и возвращает информацию о нем"""
        project_indicators = {
            'strong': [
                candidate_path / 'requirements.txt',
                candidate_path / 'package.json', 
                candidate_path / 'pom.xml',
                candidate_path / 'go.mod',
                candidate_path / 'setup.py',
                candidate_path / 'pyproject.toml',
                candidate_path / 'Cargo.toml',  
                candidate_path / 'composer.json',  
                candidate_path / 'Gemfile',  
                candidate_path / '*.csproj',
            ],
            'medium': [
                candidate_path / 'src',
                candidate_path / 'tests',
                candidate_path / 'test',
                candidate_path / 'lib',
            ],
            'weak': [
                candidate_path / 'README.md',
                candidate_path / '.gitignore',
                candidate_path / 'LICENSE',
            ]
        }

        confidence = 0.0
        language = "Unknown"

        strong_matches = []
        for ind in project_indicators['strong']:
            if ind.name == '*.csproj':
                if any(candidate_path.glob('*.csproj')):
                    strong_matches.append(Path('dummy.csproj'))
            elif ind.exists():
                strong_matches.append(ind)
                
        if strong_matches:
            confidence += len(strong_matches) * 2.0
            language = self._detect_language_from_files(strong_matches)

        medium_matches = [ind for ind in project_indicators['medium'] if ind.exists()]
        if medium_matches:
            confidence += len(medium_matches) * 1.0

        weak_matches = [ind for ind in project_indicators['weak'] if ind.exists()]
        if weak_matches:
            confidence += len(weak_matches) * 0.5

        if confidence >= 1.0:
            return ProjectInfo(candidate_path, candidate_path.name, language, confidence)
        
        return None

    def _detect_language_from_files(self, files: List[Path]) -> str:
        """Определяет язык по конфигурационным файлам"""
        lang_mapping = {
            'requirements.txt': 'Python',
            'setup.py': 'Python',
            'pyproject.toml': 'Python',
            'package.json': 'JavaScript',
            'pom.xml': 'Java',
            'build.gradle': 'Java',
            'go.mod': 'Go',
            'Cargo.toml': 'Rust',
            'composer.json': 'PHP',
            'Gemfile': 'Ruby',
            '*.csproj': 'C#',
        }
        
        for file_path in files:
            for pattern, language in lang_mapping.items():
                if pattern == '*.csproj' and file_path.name.endswith('.csproj'):
                    return language
                elif file_path.name == pattern:
                    return language
        
        return "Unknown"

    def analyze_all_projects(self) -> Dict[str, Dict]:
        """Анализирует все найденные проекты"""
        if not self.projects:
            self.discover_projects()
        
        results = {}
        for project in self.projects:
            try:
                results[project.name] = self.analyze_single_project(project.path)
            except Exception as e:
                results[project.name] = {
                    "error": str(e),
                    "project_root": str(project.path),
                    "language": project.language,
                    "status": "error"
                }
        
        return results

    def analyze_single_project(self, project_path: Union[str, Path]) -> Dict:
        """Анализирует конкретный проект"""
        project_path = Path(project_path)
        test_files = self.discover_test_files(project_path)
        test_type = self.detect_test_type(project_path)
        base_command = self.get_test_command(test_type)
        
        return {
            "project_root": str(project_path),
            "test_type": test_type.value,
            "test_type_display": test_type.name,
            "test_files_count": len(test_files),
            "test_files": [str(f.relative_to(project_path)) for f in test_files[:10]],
            "base_command": base_command,
            "project_language": self._detect_project_language(project_path),
            "commands": self._get_all_commands(test_type),
            "status": "success"
        }

    def discover_test_files(self, search_path: Path) -> List[Path]:
        """Обнаруживает тестовые файлы в указанной директории (включая подмодули)"""
        test_patterns = [
            # Python
            "**/test_*.py", "**/*_test.py", "**/test/**/*.py", "**/tests/**/*.py", "tests/**/*.py"
            # JavaScript/TypeScript
            "**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts",
            "**/test/**/*.js", "**/test/**/*.ts", "**/cypress/**/*.js", "**/cypress/**/*.ts",
            # Java - специально для структур типа Maven/Gradle
            "**/src/test/java/**/*Test.java",
            "**/src/test/java/**/*Tests.java", 
            "**/test/java/**/*Test.java",
            "**/test/java/**/*Tests.java",
            "**/test/**/*Test.java",
            "**/test/**/*Tests.java",
            "**/*Test.java",
            "**/*Tests.java",
            # Go
            "**/*_test.go",
            # C++
            "**/*_test.cpp", "**/test/**/*.cpp",
            # C#
            "**/*Test.cs", "**/test/**/*.cs",
            # PHP
            "**/*Test.php", "**/test/**/*.php",
            # Ruby
            "**/*_spec.rb", "**/test/**/*.rb",
        ]
        
        test_files = []
        for pattern in test_patterns:
            try:
                found_files = list(search_path.glob(pattern))
                test_files.extend(found_files)
            except Exception as e:
                continue
        
        # Фильтруем только файлы и убираем дубликаты
        self.test_files = list({f for f in test_files if f.is_file()})
        return self.test_files

    def detect_test_type(self, search_path: Path) -> TestType:
        """Определяет тип тестов в проекте"""
        if not self.test_files:
            self.discover_test_files(search_path)
        
        if not self.test_files:
            return TestType.UNKNOWN
        
        # Сначала определяем язык проекта по структуре и файлам конфигурации
        project_language = self._detect_project_language(search_path)
        
        # Затем анализируем тестовые файлы в контексте языка проекта
        if project_language == "Java":
            return self._detect_java_test_framework(search_path)
        elif project_language == "Python":
            return self._detect_python_test_framework(search_path)
        elif project_language in ["JavaScript", "TypeScript"]:
            return self._detect_js_test_framework(search_path)
        elif project_language == "Go":
            return self._detect_go_test_framework(search_path)
        elif project_language == "C++":
            return self._detect_cpp_test_framework(search_path)
        elif project_language == "C#":
            return self._detect_csharp_test_framework(search_path)
        elif project_language == "PHP":
            return self._detect_php_test_framework(search_path)
        elif project_language == "Ruby":
            return self._detect_ruby_test_framework(search_path)
        
        # Если язык не определился, анализируем по расширениям файлов
        extensions = {f.suffix for f in self.test_files}
        
        # Python тесты
        if any(f.suffix == '.py' for f in self.test_files):
            return self._detect_python_test_framework(search_path)
        
        # JavaScript тесты
        if any(f.suffix in ['.js', '.ts', '.jsx', '.tsx'] for f in self.test_files):
            return self._detect_js_test_framework(search_path)
        
        # Java тесты
        if any(f.suffix == '.java' for f in self.test_files):
            return self._detect_java_test_framework(search_path)
            
        # Go тесты
        if any(f.suffix == '.go' for f in self.test_files):
            return self._detect_go_test_framework(search_path)
            
        # C++ тесты
        if any(f.suffix in ['.cpp', '.cc', '.cxx'] for f in self.test_files):
            return self._detect_cpp_test_framework(search_path)
            
        # C# тесты
        if any(f.suffix == '.cs' for f in self.test_files):
            return self._detect_csharp_test_framework(search_path)
            
        # PHP тесты
        if any(f.suffix == '.php' for f in self.test_files):
            return self._detect_php_test_framework(search_path)
            
        # Ruby тесты
        if any(f.suffix == '.rb' for f in self.test_files):
            return self._detect_ruby_test_framework(search_path)
        
        return TestType.UNKNOWN

    def _detect_python_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для Python тестов"""
        # Проверяем зависимости в файлах конфигурации
        config_files = [
            search_path / "requirements.txt",
            search_path / "pyproject.toml",
            search_path / "setup.py",
            search_path / "Pipfile",
            search_path / "setup.cfg",
            search_path / "tox.ini",
        ]
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    content = config_file.read_text(encoding='utf-8', errors='ignore').lower()
                    if any(x in content for x in ["pytest", "pytest-"]):
                        return TestType.PYTEST
                    elif "nose" in content:
                        return TestType.NOSE
                    elif "fastapi" in content:
                        return TestType.FASTAPI
                    elif "django" in content:
                        return TestType.DJANGO
                    elif "flask" in content:
                        return TestType.FLASK
                    elif "starlette" in content:
                        return TestType.STARLETTE
                except:
                    continue
        
        # Проверяем структуру проекта для FastAPI
        for main_file in [search_path / "main.py", search_path / "app.py", search_path / "application.py"]:
            if main_file.exists():
                try:
                    main_content = main_file.read_text(encoding='utf-8', errors='ignore').lower()
                    if "fastapi" in main_content or "from fastapi" in main_content:
                        return TestType.FASTAPI
                    elif "flask" in main_content or "from flask" in main_content:
                        return TestType.FLASK
                except:
                    continue
        
        # Анализируем содержимое тестовых файлов
        for test_file in self.test_files[:10]:
            if test_file.suffix == '.py':
                try:
                    content = test_file.read_text(encoding='utf-8', errors='ignore').lower()
                    if any(x in content for x in ["import pytest", "from pytest", "@pytest"]):
                        return TestType.PYTEST
                    elif any(x in content for x in ["import unittest", "unittest.main", "testcase"]):
                        return TestType.UNITTEST
                    elif "import nose" in content:
                        return TestType.NOSE
                    elif any(x in content for x in ["testclient", "fastapi", "from fastapi"]):
                        return TestType.FASTAPI
                    elif any(x in content for x in ["django.test", "testcase", "from django"]):
                        return TestType.DJANGO
                    elif any(x in content for x in ["flask_testing", "flask.cli"]):
                        return TestType.FLASK
                except:
                    continue
        
        # Проверяем наличие pytest.ini или pyproject.toml с pytest конфигурацией
        if (search_path / "pytest.ini").exists():
            return TestType.PYTEST
        
        if (search_path / "pyproject.toml").exists():
            try:
                content = (search_path / "pyproject.toml").read_text(encoding='utf-8', errors='ignore')
                if "[tool.pytest]" in content or "[tool.pytest.ini_options]" in content:
                    return TestType.PYTEST
            except:
                pass
        
        return TestType.PYTEST  

    def _detect_js_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для JavaScript тестов"""
        # Проверяем package.json
        package_json = search_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                
                dependencies = {**package_data.get("dependencies", {}), 
                              **package_data.get("devDependencies", {})}
                
                if "cypress" in dependencies:
                    return TestType.CYPRESS
                elif "jest" in dependencies:
                    return TestType.JEST
                elif "mocha" in dependencies:
                    return TestType.MOCHA
                elif "vitest" in dependencies:
                    return TestType.VITEST
                elif "playwright" in dependencies:
                    return TestType.PLAYWRIGHT
                elif "jasmine" in dependencies:
                    return TestType.JASMINE
            except:
                pass
        
        # Проверяем наличие специфичных директорий и конфигурационных файлов
        if (search_path / "cypress").exists():
            return TestType.CYPRESS
        if (search_path / "playwright.config.js").exists() or (search_path / "playwright.config.ts").exists():
            return TestType.PLAYWRIGHT
        if (search_path / "jest.config.js").exists() or (search_path / "jest.config.ts").exists():
            return TestType.JEST
        if (search_path / "vitest.config.js").exists() or (search_path / "vitest.config.ts").exists():
            return TestType.VITEST
        if (search_path / ".mocharc.js").exists() or (search_path / ".mocharc.json").exists():
            return TestType.MOCHA
            
        return TestType.JEST  # По умолчанию для JS

    def _detect_java_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для Java тестов"""
        pom_xml = search_path / "pom.xml"
        if pom_xml.exists():
            try:
                content = pom_xml.read_text(encoding='utf-8', errors='ignore').lower()
                if "testng" in content:
                    return TestType.TESTNG
                elif "spock" in content:
                    return TestType.SPOCK
                elif "junit" in content:
                    return TestType.JUNIT
            except:
                pass

        build_gradle = search_path / "build.gradle"
        if build_gradle.exists():
            try:
                content = build_gradle.read_text(encoding='utf-8', errors='ignore').lower()
                if "testng" in content:
                    return TestType.TESTNG
                elif "spock" in content:
                    return TestType.SPOCK
                elif "junit" in content:
                    return TestType.JUNIT
            except:
                pass
        
        # Анализируем тестовые файлы
        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "@Test" in content and "org.testng" in content:
                    return TestType.TESTNG
                elif "extends Specification" in content or "spock.lang" in content:
                    return TestType.SPOCK
                elif "@Test" in content and "org.junit" in content:
                    return TestType.JUNIT
            except:
                continue
        
        return TestType.JUNIT  

    def _detect_go_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для Go тестов"""
        go_mod = search_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text(encoding='utf-8', errors='ignore').lower()
                if "gopkg.in/check.v1" in content:
                    return TestType.GOCHECK
                elif "github.com/stretchr/testify" in content:
                    return TestType.TESTIFY
            except:
                pass

        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "import .gopkg.in/check.v1" in content or "gocheck" in content:
                    return TestType.GOCHECK
                elif "github.com/stretchr/testify" in content:
                    return TestType.TESTIFY
            except:
                continue
        
        return TestType.GO_TEST  

    def _detect_cpp_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для C++ тестов"""
        cmake_file = search_path / "CMakeLists.txt"
        if cmake_file.exists():
            try:
                content = cmake_file.read_text(encoding='utf-8', errors='ignore')
                if "gtest" in content or "GTest" in content:
                    return TestType.GOOGLE_TEST
                elif "catch2" in content:
                    return TestType.CATCH2
                elif "boost_test" in content:
                    return TestType.BOOST_TEST
            except:
                pass

        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "#include <gtest/gtest.h>" in content or "TEST_F" in content:
                    return TestType.GOOGLE_TEST
                elif "#include <catch2/catch.hpp>" in content or "CATCH_TEST_CASE" in content:
                    return TestType.CATCH2
                elif "#include <boost/test/unit_test.hpp>" in content:
                    return TestType.BOOST_TEST
                elif "#include <cppunit/" in content:
                    return TestType.CPPUNIT
            except:
                continue
        
        return TestType.GOOGLE_TEST  

    def _detect_csharp_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для C# тестов"""
        for csproj in search_path.glob("**/*.csproj"):
            try:
                content = csproj.read_text(encoding='utf-8', errors='ignore').lower()
                if "nunit" in content:
                    return TestType.NUNIT
                elif "xunit" in content:
                    return TestType.XUNIT
                elif "mstest" in content:
                    return TestType.MSTEST
            except:
                continue
        
        # Анализируем тестовые файлы
        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "[TestFixture]" in content or "using NUnit.Framework" in content:
                    return TestType.NUNIT
                elif "[Fact]" in content or "using Xunit" in content:
                    return TestType.XUNIT
                elif "[TestMethod]" in content or "using Microsoft.VisualStudio.TestTools.UnitTesting" in content:
                    return TestType.MSTEST
            except:
                continue
        
        return TestType.NUNIT  

    def _detect_php_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для PHP тестов"""
        composer_json = search_path / "composer.json"
        if composer_json.exists():
            try:
                with open(composer_json, 'r', encoding='utf-8') as f:
                    composer_data = json.load(f)
                dependencies = {**composer_data.get("require", {}), 
                              **composer_data.get("require-dev", {})}
                if "phpunit/phpunit" in dependencies:
                    return TestType.PHPUNIT
            except:
                pass
        
        # Анализируем тестовые файлы
        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "PHPUnit\\Framework\\TestCase" in content or "use PHPUnit\\Framework\\TestCase" in content:
                    return TestType.PHPUNIT
            except:
                continue
        
        return TestType.PHPUNIT  

    def _detect_ruby_test_framework(self, search_path: Path) -> TestType:
        """Определяет фреймворк для Ruby тестов"""
        gemfile = search_path / "Gemfile"
        if gemfile.exists():
            try:
                content = gemfile.read_text(encoding='utf-8', errors='ignore')
                if "rspec" in content:
                    return TestType.RSPEC
                elif "minitest" in content:
                    return TestType.MINITEST
            except:
                pass
        
        # Проверяем наличие конфигурационных файлов
        if (search_path / "spec").exists() or (search_path / ".rspec").exists():
            return TestType.RSPEC
        if (search_path / "test").exists():
            return TestType.MINITEST
        
        # Анализируем тестовые файлы
        for test_file in self.test_files[:5]:
            try:
                content = test_file.read_text(encoding='utf-8', errors='ignore')
                if "describe" in content and "RSpec" in content:
                    return TestType.RSPEC
                elif "Minitest::Test" in content or "MiniTest::Unit::TestCase" in content:
                    return TestType.MINITEST
            except:
                continue
        
        return TestType.RSPEC  

    def get_test_command(self, test_type: TestType, specific_file: Optional[str] = None, 
                        additional_args: str = "") -> str:
        """Генерирует команду для запуска тестов"""
        base_commands = {
            # Python
            TestType.PYTEST: "pytest",
            TestType.UNITTEST: "python -m unittest",
            TestType.NOSE: "nosetests",
            TestType.DJANGO: "python manage.py test",
            TestType.FASTAPI: "pytest",
            TestType.FLASK: "pytest",
            TestType.STARLETTE: "pytest",
            
            # JavaScript
            TestType.JEST: "npx jest",
            TestType.MOCHA: "npx mocha",
            TestType.JASMINE: "npx jasmine",
            TestType.CYPRESS: "npx cypress run",
            TestType.PLAYWRIGHT: "npx playwright test",
            TestType.VITEST: "npx vitest run",
            
            # Java
            TestType.JUNIT: "mvn test",
            TestType.TESTNG: "mvn test",
            TestType.SPOCK: "./gradlew test",
            TestType.MAVEN_SUREFIRE: "mvn test",
            
            # Go
            TestType.GO_TEST: "go test",
            TestType.GOCHECK: "go test",
            TestType.TESTIFY: "go test",
            
            # C++
            TestType.GOOGLE_TEST: "./run_tests",
            TestType.CATCH2: "./tests",
            TestType.BOOST_TEST: "./test_runner",
            TestType.CPPUNIT: "./test_runner",
            
            # C#
            TestType.NUNIT: "dotnet test",
            TestType.XUNIT: "dotnet test",
            TestType.MSTEST: "dotnet test",
            
            # PHP
            TestType.PHPUNIT: "./vendor/bin/phpunit",
            
            # Ruby
            TestType.RSPEC: "bundle exec rspec",
            TestType.MINITEST: "bundle exec rake test",
        }
        
        command = base_commands.get(test_type, "echo 'Тип тестов не поддерживается'")
        
        if specific_file:
            command += f" {specific_file}"
        
        if additional_args:
            command += f" {additional_args}"
        
        return command

    def _detect_project_language(self, search_path: Path) -> str:
        """Определяет язык проекта"""
        file_extensions = {}
        try:
            for file_path in search_path.rglob("*.*"):
                if file_path.is_file():
                    ext = file_path.suffix
                    if ext:
                        file_extensions[ext] = file_extensions.get(ext, 0) + 1
        except:
            pass

        lang_patterns = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.go': 'Go',
            '.cpp': 'C++',
            '.cc': 'C++',
            '.cxx': 'C++',
            '.cs': 'C#',
            '.php': 'PHP',
            '.rb': 'Ruby',
        }
        
        for ext, count in sorted(file_extensions.items(), key=lambda x: x[1], reverse=True):
            if ext in lang_patterns:
                return lang_patterns[ext]
        
        return "Unknown"

    def _get_all_commands(self, test_type: TestType) -> Dict[str, str]:
        """Генерирует все возможные команды для типа тестов"""
        commands = {
            "all_tests": self.get_test_command(test_type),
            "with_verbose": self.get_test_command(test_type, additional_args="-v"),
            "specific_file": self.get_test_command(test_type, specific_file="<test_file>"),
        }
        
        # Добавляем специфичные команды для разных фреймворков
        if test_type in [TestType.PYTEST, TestType.FASTAPI, TestType.FLASK, TestType.STARLETTE]:
            commands.update({
                "with_coverage": "pytest --cov=.",
                "with_markers": "pytest -m <marker>",
                "failed_only": "pytest --lf",
            })
        elif test_type == TestType.JEST:
            commands.update({
                "with_coverage": "npx jest --coverage",
                "watch_mode": "npx jest --watch",
            })
        elif test_type == TestType.GO_TEST:
            commands.update({
                "with_verbose": "go test -v",
                "with_coverage": "go test -cover",
                "specific_package": "go test ./<package>",
            })
        elif test_type in [TestType.JUNIT, TestType.TESTNG]:
            commands.update({
                "with_maven": "mvn test",
                "with_gradle": "./gradlew test",
                "specific_test": "mvn test -Dtest=<TestClass>",
            })
        
        return commands

# Функции для удобного использования
def analyze_all_projects(base_path: str = ".") -> Dict[str, Dict]:
    """Анализирует все проекты в указанной директории"""
    framework = TestFramework(base_path)
    return framework.analyze_all_projects()

def analyze_single_project(project_path: str) -> Dict:
    """Анализирует конкретный проект"""
    framework = TestFramework(project_path)
    return framework.analyze_single_project(project_path)

def discover_projects(base_path: str = ".") -> List[Dict]:
    """Только обнаруживает проекты без детального анализа"""
    framework = TestFramework(base_path)
    projects = framework.discover_projects()
    return [{"name": p.name, "path": str(p.path), "language": p.language, "confidence": p.confidence} for p in projects]

def get_test_command_for_file(project_path: str, test_file: str, additional_args: str = "") -> str:
    """Получить команду для запуска конкретного тестового файла"""
    framework = TestFramework(project_path)
    project_root = framework.discover_projects()[0].path if framework.discover_projects() else Path(project_path)
    test_type = framework.detect_test_type(project_root)
    return framework.get_test_command(test_type, test_file, additional_args)

# Пример использования
if __name__ == "__main__":
    base_directory = "."  # Текущая директория со склонированными проектами
    
    print("🔍 Поиск всех проектов...")
    projects = discover_projects(base_directory)
    
    print(f"📁 Найдено проектов: {len(projects)}")
    for i, project in enumerate(projects, 1):
        print(f"  {i}. {project['name']} ({project['language']}) - уверенность: {project['confidence']:.1f}")
    
    if projects:
        print(f"\n🧪 Анализируем все проекты...")
        results = analyze_all_projects(base_directory)
        
        for project_name, analysis in results.items():
            print(f"\n🎯 Проект: {project_name}")
            
            if analysis.get("status") == "error":
                print(f"   ❌ Ошибка: {analysis['error']}")
                continue
                
            print(f"   🌐 Язык: {analysis['project_language']}")
            print(f"   🧪 Тип тестов: {analysis['test_type_display']}")
            print(f"   🚀 Команда: {analysis['base_command']}")

    else:
        print("❌ Проекты не найдены")