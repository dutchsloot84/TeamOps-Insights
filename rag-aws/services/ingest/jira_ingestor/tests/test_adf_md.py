import textwrap

from services.ingest.jira_ingestor.adf_md import to_markdown


def test_to_markdown_renders_common_nodes():
    adf = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Heading"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "This is "},
                    {
                        "type": "text",
                        "text": "bold",
                        "marks": [{"type": "strong"}],
                    },
                    {"type": "text", "text": " and "},
                    {
                        "type": "text",
                        "text": "italic",
                        "marks": [{"type": "em"}],
                    },
                    {"type": "text", "text": " with "},
                    {
                        "type": "text",
                        "text": "code",
                        "marks": [{"type": "code"}],
                    },
                    {"type": "text", "text": " and "},
                    {
                        "type": "text",
                        "text": "a link",
                        "marks": [
                            {
                                "type": "link",
                                "attrs": {"href": "https://example.com"},
                            }
                        ],
                    },
                    {"type": "text", "text": "."},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "First"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Second"}],
                            }
                        ],
                    },
                ],
            },
            {
                "type": "orderedList",
                "attrs": {"order": 1},
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "One"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Two"}],
                            }
                        ],
                    },
                ],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "print('hello')"}],
            },
        ],
    }

    markdown = to_markdown(adf)
    assert (
        markdown
        == textwrap.dedent(
            """\
        ## Heading

        This is **bold** and *italic* with `code` and [a link](https://example.com).

        - First
        - Second

        1. One
        2. Two

        ```python
        print('hello')
        ```
        """
        ).strip()
    )


def test_to_markdown_collapses_empty_nodes():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": []},
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Hello"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Line"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Two"},
                ],
            },
        ],
    }

    markdown = to_markdown(adf)
    assert markdown == "Hello\n\nLine\nTwo"
