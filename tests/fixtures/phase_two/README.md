# Phase Two Generated Fixtures

Attachment parser tests generate synthetic PDF, XLSX, DOCX, and PNG inputs inside
`TemporaryDirectory` at test time. This directory intentionally contains no
attachment binaries and no customer data.
