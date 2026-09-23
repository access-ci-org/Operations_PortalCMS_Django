from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase
from djangocms_text.cms_plugins import TextPlugin
from djangocms_text.widgets import TextEditorWidget


class PlaceholderPluginConfigurationTests(SimpleTestCase):
    def test_picture_is_available_standalone_and_embedded_in_text(self):
        configurations = settings.CMS_PLACEHOLDER_CONF.values()
        text_and_picture_configurations = [
            configuration
            for configuration in configurations
            if {'TextPlugin', 'PicturePlugin'} <= set(configuration['plugins'])
        ]

        self.assertTrue(text_and_picture_configurations)
        for configuration in text_and_picture_configurations:
            self.assertIn('PicturePlugin', configuration['plugins'])
            self.assertIn(
                'PicturePlugin',
                configuration['child_classes']['TextPlugin'],
            )

    def test_existing_supported_text_child_rules_are_preserved(self):
        child_plugins = settings.CMS_PLACEHOLDER_CONF['content'][
            'child_classes'
        ]['TextPlugin']

        self.assertEqual(
            child_plugins,
            [
                'PicturePlugin',
                'LinkPlugin',
                'FilePlugin',
                'VideoPlayerPlugin',
            ],
        )

    def test_cms_plugin_add_dropdown_is_available_in_text_editor(self):
        widget = TextEditorWidget(placeholder=SimpleNamespace(pk=1))
        editor_options = widget.get_editor_settings('en')['options']
        toolbar_buttons = {
            button
            for group in editor_options['toolbar']
            for button in group
        }

        self.assertIn('CMSPlugins', toolbar_buttons)
        self.assertNotIn('cmsplugins', toolbar_buttons)
        self.assertNotIn('removeButtons', editor_options)

    def test_plugins_remain_available_as_standalone_content(self):
        standalone_plugins = set(
            settings.CMS_PLACEHOLDER_CONF['content']['plugins']
        )

        self.assertTrue(
            {
                'PicturePlugin',
                'FilePlugin',
                'LinkPlugin',
                'VideoPlayerPlugin',
            } <= standalone_plugins
        )

    def test_runtime_text_plugin_menu_is_limited_to_common_content(self):
        child_plugins = TextPlugin.get_child_classes('content')

        self.assertEqual(
            set(child_plugins),
            {
                'PicturePlugin',
                'LinkPlugin',
                'FilePlugin',
                'VideoPlayerPlugin',
            },
        )

    def test_pasted_base64_images_are_disabled(self):
        self.assertIsNone(settings.TEXT_SAVE_IMAGE_FUNCTION)

    def test_dedicated_image_slots_still_allow_picture_plugin(self):
        for slot in ('feature_image', 'hero_image', 'featured_image'):
            self.assertEqual(
                settings.CMS_PLACEHOLDER_CONF[slot]['plugins'],
                ['PicturePlugin'],
            )
