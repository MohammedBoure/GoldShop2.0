# Client Credit Manager

This package manages client credit staging, publication, and manual credit records.

- `__init__.py`: Exposes `ClientCreditManager` by composing the package mixins.
- `base.py`: Shared database helpers and common credit utilities.
- `manual.py`: Manual client credit creation and direct credit operations.
- `publish.py`: Publishing logic that converts staged credit data into committed records.
- `security.py`: Permission and authorization helpers for client credit workflows.
- `staging.py`: Review/staging operations used before credit data is published.

