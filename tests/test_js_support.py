"""Tests for JS/TS multi-language analyzer support."""

import pytest

from vibediff.analyze import analyze_ai
from vibediff.collaboration import analyze_collaboration
from vibediff.diff import Diff, FileDiff, Hunk
from vibediff.idiom import analyze_idioms


def _js_file(path, lines):
    return FileDiff(
        path=path,
        language="javascript" if path.endswith(".js") else "typescript",
        hunks=[Hunk(1, 0, 1, len(lines), added=lines, removed=[], context=[])],
    )


def _diff(files):
    return Diff(files=files)


class TestJSCommentDetection:
    def test_js_restating_comments(self):
        lines = [
            "// Initialize the application",
            "const app = express();",
            "// Get the user data",
            "const data = fetchUser();",
            "// Check if the request is valid",
            "if (!req.body) return;",
            "// Handle the response",
            "res.send(result);",
            "// Update the database",
            "db.save(record);",
        ]
        report = analyze_ai(_diff([_js_file("app.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "restating_comments" in signals

    def test_js_section_headers(self):
        lines = [
            "// --- imports ---",
            "import express from 'express';",
            "// --- routes ---",
            "app.get('/', handler);",
            "// --- middleware ---",
            "app.use(cors());",
            "const server = app.listen(3000);",
        ]
        report = analyze_ai(_diff([_js_file("app.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "section_headers" in signals

    def test_js_high_comment_density(self):
        lines = [
            "// Set up the server",
            "const app = express();",
            "// Configure middleware",
            "app.use(cors());",
            "// Handle routes",
            "app.get('/', handler);",
            "// Start listening",
            "app.listen(3000);",
        ]
        report = analyze_ai(_diff([_js_file("server.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "comment_density" in signals


class TestJSNamingDetection:
    def test_js_verbose_function_names(self):
        lines = [
            "function handleIncomingUserRequest(req) { return req; }",
            "function processOutgoingDataResponse(data) { return data; }",
            "function validateInputFormFields(form) { return form; }",
            "function initializeApplicationState(state) { return state; }",
            "function fetchRemoteDatabaseRecords(db) { return db; }",
        ]
        report = analyze_ai(_diff([_js_file("api.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "verbose_names" in signals

    def test_js_const_arrow_functions(self):
        lines = [
            "const handleIncomingUserRequest = async (req) => req;",
            "const processOutgoingDataResponse = (data) => data;",
            "const validateInputFormFields = (form) => form;",
            "const initializeApplicationState = (state) => state;",
            "const fetchRemoteDatabaseRecords = async (db) => db;",
        ]
        report = analyze_ai(_diff([_js_file("api.ts", lines)]))
        signals = {f.signal for f in report.findings}
        assert "verbose_names" in signals


class TestJSStructureDetection:
    def test_js_null_guards(self):
        lines = [
            "function handleA(x) {",
            "  if (x === null) return;",
            "  return x;",
            "}",
            "function handleB(y) {",
            "  if (y === undefined) return;",
            "  return y;",
            "}",
            "function handleC(z) {",
            "  if (z !== null) {",
            "    return z;",
            "  }",
            "}",
        ]
        report = analyze_ai(_diff([_js_file("utils.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "excessive_guards" in signals

    def test_js_broad_catch(self):
        lines = [
            "function doA() {",
            "  try { fetch('/a'); } catch (e) { console.log(e); }",
            "}",
            "function doB() {",
            "  try { fetch('/b'); } catch (err) { console.log(err); }",
            "}",
        ]
        report = analyze_ai(_diff([_js_file("api.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "broad_exceptions" in signals


class TestJSIdiomDetection:
    def test_snake_case_in_js(self):
        lines = [
            "const user_name = 'test';",
            "function get_user_data() { return null; }",
            "let response_body = {};",
            "const api_endpoint = '/users';",
        ]
        report = analyze_idioms(_diff([_js_file("app.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "snake_case_in_js" in signals

    def test_java_patterns_in_js(self):
        lines = [
            "class UserFactory {",
            "  create() { return new User(); }",
            "}",
            "class ConnectionManager {",
            "  connect() { return null; }",
            "}",
        ]
        report = analyze_idioms(_diff([_js_file("patterns.ts", lines)]))
        signals = {f.signal for f in report.findings}
        assert "java_patterns_in_js" in signals

    def test_clean_js_no_idiom_issues(self):
        lines = [
            "const app = express();",
            "app.get('/', (req, res) => res.send('ok'));",
            "app.listen(3000);",
        ]
        report = analyze_idioms(_diff([_js_file("app.js", lines)]))
        assert report.idiom_score == 0


class TestJSCollaborationDetection:
    def test_js_generic_names(self):
        lines = [
            "const data = fetch('/api');",
            "const result = process(data);",
            "const output = format(result);",
            "const response = send(output);",
            "const value = parse(response);",
            "const item = get(value);",
        ]
        report = analyze_collaboration(_diff([_js_file("app.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "generic_names" in signals

    def test_js_generic_tests(self):
        lines = [
            "it('should work', () => {",
            "  expect(true).toBe(true);",
            "});",
            "test('does something', () => {",
            "  expect(1).toBe(1);",
            "});",
        ]
        report = analyze_collaboration(_diff([_js_file("app.test.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "generic_tests" in signals

    def test_js_placeholders(self):
        lines = [
            "function a() { throw new Error('Not implemented'); }",
            "function b() { throw new Error('TODO'); }",
            "function c() { throw new Error('Not implemented'); }",
        ]
        report = analyze_collaboration(_diff([_js_file("stubs.ts", lines)]))
        signals = {f.signal for f in report.findings}
        assert "placeholders" in signals

    def test_js_todo_comments(self):
        lines = [
            "// TODO: fix this later",
            "const x = 1;",
            "// TODO: refactor",
            "const y = 2;",
        ]
        report = analyze_collaboration(_diff([_js_file("app.js", lines)]))
        signals = {f.signal for f in report.findings}
        assert "unresolved_todos" in signals
