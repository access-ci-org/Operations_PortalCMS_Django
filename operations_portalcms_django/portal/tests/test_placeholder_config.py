from django.conf import settings
from django.test import SimpleTestCase
from djangocms_text_ckeditor.cms_plugins import TextPlugin


class PlaceholderPluginConfigurationTests(SimpleTestCase):
    def test_picture_remains_standalone_but_not_embedded_in_text(self):
        configurations = settings.CMS_PLACEHOLDER_CONF.values()
        text_and_picture_configurations = [
            configuration
            for configuration in configurations
            if {'TextPlugin', 'PicturePlugin'} <= set(configuration['plugins'])
        ]

        self.assertTrue(text_and_picture_configurations)
        for configuration in text_and_picture_configurations:
            self.assertIn('PicturePlugin', configuration['plugins'])
            self.assertNotIn(
                'PicturePlugin',
                configuration['child_classes']['TextPlugin'],
            )

    def test_other_supported_text_children_remain_available(self):
        child_plugins = settings.CMS_PLACEHOLDER_CONF['content'][
            'child_classes'
        ]['TextPlugin']

        self.assertEqual(
            child_plugins,
            ['LinkPlugin', 'FilePlugin', 'VideoPlayerPlugin'],
        )

    def test_runtime_text_plugin_menu_excludes_picture(self):
        child_plugins = TextPlugin.get_child_classes('content')

        self.assertNotIn('PicturePlugin', child_plugins)
        self.assertEqual(
            set(child_plugins),
            {'LinkPlugin', 'FilePlugin', 'VideoPlayerPlugin'},
        )

    def test_dedicated_image_slots_still_allow_picture_plugin(self):
        for slot in ('feature_image', 'hero_image', 'featured_image'):
            self.assertEqual(
                settings.CMS_PLACEHOLDER_CONF[slot]['plugins'],
                ['PicturePlugin'],
            )
