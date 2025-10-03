# Good First Issues for Contributors

---

## 1. Retry/Backoff Logic for API Calls

### 📝 Description
Implement retry and exponential backoff for failed API calls to improve reliability during network instability.

### 🎯 Acceptance Criteria
- [ ] Add retry mechanism with configurable max attempts  
- [ ] Implement exponential backoff (e.g., 2^n)  
- [ ] Tests cover success, retry, and max failure scenarios  

### ✅ Difficulty
- [ ] Easy  
- [x] Medium  

### 📂 Files / Modules Involved
- API client module(s)

### 🔗 Resources
- Example backoff logic: https://en.wikipedia.org/wiki/Exponential_backoff

---

## 2. Redaction Rules for Sensitive Logs

### 📝 Description
Create a system to redact sensitive information (tokens, passwords, keys) from logs.

### 🎯 Acceptance Criteria
- [ ] Define regex-based rule set for sensitive fields  
- [ ] Replace matches with "***" in logs  
- [ ] Add unit tests confirming redaction  

### ✅ Difficulty
- [ ] Easy  
- [x] Medium  

### 📂 Files / Modules Involved
- Logging utilities

### 🔗 Resources
- OWASP logging guidelines: https://owasp.org/www-project-cheat-sheets/cheatsheets/Logging_Cheat_Sheet.html

---

## 3. Unit Tests for Index Writer

### 📝 Description
Add missing unit tests for the `IndexWriter` module to ensure correct indexing behavior.

### 🎯 Acceptance Criteria
- [ ] Tests for write, update, and delete scenarios  
- [ ] Verify index persistence after operations  
- [ ] Mock dependencies where required  

### ✅ Difficulty
- [x] Easy  
- [ ] Medium  

### 📂 Files / Modules Involved
- `IndexWriter` source and test files

### 🔗 Resources
- Jest (if JavaScript): https://jestjs.io/docs/getting-started  

---

## 4. Troubleshooting Guide for Projects v2

### 📝 Description
Create a contributor-facing guide to resolve common errors in Projects v2 setup.

### 🎯 Acceptance Criteria
- [ ] Document setup steps and common pitfalls  
- [ ] Add troubleshooting section in `/docs`  
- [ ] Include examples with error messages and fixes  

### ✅ Difficulty
- [x] Easy  
- [ ] Medium  

### 📂 Files / Modules Involved
- `/docs/projects-v2.md` (new file)

### 🔗 Resources
- GitHub Projects v2 documentation: https://docs.github.com/en/issues/planning-and-tracking-with-projects

---

## 5. JSON Index Schema Documentation

### 📝 Description
Add documentation for JSON index schema (fields, types, constraints).

### 🎯 Acceptance Criteria
- [ ] Document all supported fields in schema  
- [ ] Provide JSON examples  
- [ ] Add section to official docs  

### ✅ Difficulty
- [x] Easy  
- [ ] Medium  

### 📂 Files / Modules Involved
- `/docs/schema.md`

### 🔗 Resources
- JSON schema docs: https://json-schema.org/understanding-json-schema/

---

## 6. Lint Rule for Consistent Error Messages

### 📝 Description
Introduce a linting rule to enforce consistent error message style.

### 🎯 Acceptance Criteria
- [ ] Define rule (e.g., start with capital letter, no trailing period)  
- [ ] Integrate with CI  
- [ ] Add docs for rule  

### ✅ Difficulty
- [ ] Easy  
- [x] Medium  

### 📂 Files / Modules Involved
- Linter config files (`.eslintrc.js`, etc.)

### 🔗 Resources
- ESLint rule creation: https://eslint.org/docs/latest/developer-guide/working-with-rules  

---

## 7. Retry Tests for API Client

### 📝 Description
Extend test suite to simulate failures and confirm retry/backoff logic works correctly.

### 🎯 Acceptance Criteria
- [ ] Mock server to simulate timeouts  
- [ ] Verify client retries with exponential delay  
- [ ] Ensure proper error thrown after max retries  

### ✅ Difficulty
- [x] Easy  
- [ ] Medium  

### 📂 Files / Modules Involved
- API client test files

### 🔗 Resources
- Nock (for HTTP mocking): https://github.com/nock/nock  

---

## 8. Prettier Config for Code Formatting

### 📝 Description
Introduce Prettier config for consistent code formatting across the repo.

### 🎯 Acceptance Criteria
- [ ] Add `.prettierrc` with repo-wide defaults  
- [ ] Update contributing guide  
- [ ] Add CI check for formatting  

### ✅ Difficulty
- [x] Easy  
- [ ] Medium  

### 📂 Files / Modules Involved
- `.prettierrc`  
- `.github/workflows/ci.yml`  

### 🔗 Resources
- Prettier docs: https://prettier.io/docs/en/configuration.html  
