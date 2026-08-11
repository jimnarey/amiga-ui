---
name: code-style
description: >
  Follow the repository's Python code style and structure conventions. Use when
  adding or editing Python modules, tests, CLI code, runtime helpers, or
  launcher logic.
---

# Code Style

## Use This Skill When
- Writing Python or changing existing Python code in any way

## Goal
Conform to sound coding practices and the standards of this project.

### Typing
- Use type annotations for all functions and methods.
- Use type annotations for variables when the type checker requires it or when they add readability.
- Assume Python version 3.12 or greater and prefer modern syntax, even if it reduces compatibility.
- Prefer `type` aliases for named unions or backend-specific types.
- Prefer `Protocol` over `ABC` where structural typing preserves implementation flexibility.

### Design
- Prefer small, named helper functions over long blocks of inline logic.
- Keep functions pure and methods static and pure where possible.
- Keep public methods thin where practical; move reusable logic into named helper functions.
- Where logic can be extracted into a domain-neutral, generic form do so. Maintain in domain-neutral modules.
- Put validation logic in validation modules rather than scattering guards through operations.
- Don't be afraid to use classes where they are the right tool, but prefer disciplined procedural code over unnecessary OOP.
- Prefer dataclasses over dictionaries when representing structured data.
- Prefer a series of `if` statements with early returns over an `if`/`elif`/`else` chain.

### Tests
- Use the `unittest` module.
- All non-trivial functions and methods should have tests.
- Tiny private helpers may be covered through the public or helper function that owns their behaviour.
- Prefer one test class per method or function.
- Prefer `subTest` for multiple cases within the same behaviour.
- Prefer slight over-testing over slight under-testing.
- Prefer behavioural tests over implementation-detail tests.
- Where functions or methods call other functions or methods in the project, prefer an integration-style test over mocking.
- Prefer happy-path and non-happy-path tests grouped by theme rather than separated mechanically.
- Prefer inline or filesystem fixtures over dynamically generated test data.
- Empty test stubs should use `pass`, not `...`.
- Do not add empty lines inside test methods.

### Docstrings And Comments
- Add module docstrings.
- Add docstrings when they explain behaviour, design intent, edge cases, or non-obvious calculations that are not clear from the name and code.
- Do not add docstrings to classes unless they are needed to navigate the code.
- Use comments sparingly, only where code is genuinely complex or where an implementation or design choice needs explanation.

### Editing Discipline
- Make small, targeted edits.
- Do not rewrite unrelated code while making a requested change.
- Do not edit installed packages under `.venv/`.
- Use ASCII unless the file already requires something else.

### Validation
- Confirm added or edited code works by running `python -m py_compile` against edited files where useful.
- Run the relevant focused tests after making a change.
- Run the full test suite when the change is broad, structural, or likely to affect multiple modules.
- If tests or checks cannot be run, say so clearly.