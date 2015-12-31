import os

from compressor.filters import CompilerFilter
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.temp import NamedTemporaryFile


class BaseCompiler(CompilerFilter):
    infile_ext = ''

    def input(self, **kwargs):
        """
        Specify temporary input file extension.

        Browserify requires explicit file extension (".js" or ".json" by default).
        https://github.com/substack/node-browserify/issues/1469
        """
        if self.infile is None and "{infile}" in self.command:
            if self.filename is None:
                self.infile = NamedTemporaryFile(mode='wb', suffix=self.infile_ext)
                self.infile.write(self.content.encode(self.default_encoding))
                self.infile.flush()
                self.options += (
                    ('infile', self.infile.name),
                )
        return super(BaseCompiler, self).input(**kwargs)

    @staticmethod
    def get_all_static():
        """
        Get all the static files directories found by ``STATICFILES_FINDERS``

        :return: set of paths (top-level folders only)
        """
        static_dirs = set()

        for finder in settings.STATICFILES_FINDERS:
            finder = finders.get_finder(finder)

            if hasattr(finder, 'storages'):
                for storage in finder.storages.values():
                    static_dirs.add(storage.location)

            if hasattr(finder, 'storage'):
                static_dirs.add(finder.storage.location)

        return static_dirs


class SCSSCompiler(BaseCompiler):
    """
    django-compressor pre-compiler for SCSS files.

    Consists of 2 steps:

    1. ``node-sass input.scss output.css``
    2. ``postcss --use autoprefixer -r output.css``
    """
    command = (
        'node-sass --output-style expanded {paths} {infile} {outfile} && '
        'postcss --use autoprefixer --autoprefixer.browsers "ie >= 9, > 5%" -r {outfile}'
    )

    infile_ext = '.scss'

    def __init__(self, content, attrs, *args, **kwargs):
        """
        Include all available 'static' dirs:

            node-sass --include-path path/to/app-1/static/ --include-path path/to/app-2/static/ ...

        So you can do imports inside your SCSS files:

            @import "app-1/scss/mixins";
            @import "app-2/scss/variables";

            .page-title {
                font-size: $title-font-size;
            }
        """
        self.options += (
            ('paths', ' '.join(['--include-path {}'.format(s) for s in self.get_all_static()])),
        )

        super(SCSSCompiler, self).__init__(content, self.command, *args, **kwargs)


class ES6Compiler(BaseCompiler):
    """
    django-compressor pre-compiler for ES6 files.

    Transforms ES6 to ES5 using Browserify + Babel.
    """
    command = (
        'export NODE_PATH={paths} && '
        'browserify "{infile}" -o "{outfile}" --no-bundle-external --node '
        '-t [ {node_modules}/babelify --presets={node_modules}/babel-preset-es2015 ]'
    )

    infile_ext = '.js'

    def __init__(self, content, attrs, *args, **kwargs):
        """
        Include all available 'static' dirs:

            export NODE_PATH="path/to/app-1/static/:path/to/app-2/static/" && browserify ...

        So you can do imports inside your ES6 modules:

            import controller from 'app-1/page-controller';
            import { login, signup } from 'app-2/pages';

            controller.registerPages(login, signup);
        """
        self.options += (
            ('node_modules', getattr(settings, 'COMPRESS_NODE_MODULES', '/usr/lib/node_modules')),
            ('paths', os.pathsep.join(self.get_all_static())),
        )

        super(ES6Compiler, self).__init__(content, self.command, *args, **kwargs)
