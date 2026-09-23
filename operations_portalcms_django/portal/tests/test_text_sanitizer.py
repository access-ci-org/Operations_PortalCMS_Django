from django.test import SimpleTestCase

from djangocms_text.html import clean_html


class TextSanitizerTests(SimpleTestCase):
    def test_preserves_existing_content_formatting_and_removes_scripts(self):
        cleaned = clean_html(
            '<p class="lead">Hello <strong>world</strong></p>'
            '<script>alert(1)</script>'
        )

        self.assertIn(
            '<p class="lead">Hello <strong>world</strong></p>', cleaned
        )
        self.assertNotIn('<script', cleaned)
        self.assertNotIn('alert(1)', cleaned)

    def test_preserves_configured_video_iframe_attributes(self):
        cleaned = clean_html(
            '<iframe src="https://www.youtube.com/embed/example" '
            'title="Example video" width="560" height="315" '
            'scrolling="no" allow="fullscreen" allowfullscreen '
            'frameborder="0" referrerpolicy="strict-origin" '
            'loading="lazy"></iframe>'
        )

        self.assertIn('<iframe', cleaned)
        self.assertIn('src="https://www.youtube.com/embed/example"', cleaned)
        self.assertIn('title="Example video"', cleaned)
        self.assertIn('allowfullscreen=""', cleaned)
        self.assertIn('referrerpolicy="strict-origin"', cleaned)
