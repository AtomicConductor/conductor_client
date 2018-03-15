import os
import logging
import itertools
import re
import shlex
import xgenm
from maya import cmds
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

'''
Notes on terminology.

Between maya's docs, maya's api, and xgen's api, there several different terms that are used but
actually refer to the same thing:

"palette" == "collection"
"module" == "object"



'''


'''    
for palette in xgenm.palettes():
    for description in xgenm.descriptions(palette):       
        prim_description = xgenm.getActive(palette, description, "Primitive")
        
        
from conductor.lib import xgen_utils
reload(xgen_utils)

paths = []

for palette_node in cmds.ls(type="xgmPalette")
    palette_paths = sgen_utils.scrape_palette(palette_node)
    paths.extend(palette_paths)

        
'''


def str_to_bool(string):
    return string.lower() in ['true', '1']


def get_xgen_data():
    xgen_data = []
    # ---- PALETTES ----
    for palette_name in xgenm.palettes():
        print "\npalette_name: %s" % palette_name
        palette_data = get_palette_data(palette_name)
        for attr_name, attr_value in palette_data.iteritems():
            print "\t%s.%s=%s" % (palette_name, attr_name, attr_value)
        palette_data["descriptions"] = []
        xgen_data.append(palette_data)

        # ---- DESCRIPTIONS ----
        descriptions = xgenm.descriptions(palette_name)
        print "\tdescriptions: %s" % (descriptions, )
        for description_name in descriptions:
            description_data = get_description_data(palette_name, description_name)
            for attr_name, attr_value in description_data.iteritems():
                print "\t\t%s.%s.%s=%s" % (palette_name, description_name, attr_name, attr_value)

            description_data["objects"] = []
            palette_data["descriptions"].append(description_data)
            # ----  OBJECTS ----
            objects = xgenm.objects(palette_name, description_name)
            print "\t\tobjects: %s" % (objects, )
            for object_name in objects:
                object_data = get_object_data(palette_name, description_name, object_name)
                for attr_name, attr_value in object_data.iteritems():
                    print "\t\t\t%s.%s.%s.%s=%s" % (palette_name, description_name, object_name, attr_name, attr_value)
                description_data["objects"].append(object_data)

    return xgen_data


def scrape_xgen():
    '''
    Default maya behavior is to create an "xgen" directory at the root of the maya project


    For each xgenPallete node in the maya scene:
        1. Query for the palette (collection) .xgen file


    .xgen files

    vars
        {DESC}
        {PROJECT}


    xgmPallete ("Palette"/"Collection")
        xgmDescription  ("Description")
            xgmSubdPatch (")


    Include all files in 
        DESC


    '''
    paths = []

    config_filepath = get_config_file()
    if config_filepath:
        logger.debug("Found xgen config: %s", config_filepath)
        paths.append(config_filepath)

    for palette_node in cmds.ls(type="xgmPalette"):
        palette_paths = scrape_palette(str(palette_node))
        paths.extend(palette_paths)

    return paths


def get_config_file():
    '''
    Xgen uses o
    '''
    logger.debug("Searching for xgen config.txt from $XGEN_CONFIG_PATH")
    config_dirpath = os.environ.get("XGEN_CONFIG_PATH") or ""
    config_filepath = os.path.join(config_dirpath, "config.txt")
    if config_dirpath and os.path.isfile(config_filepath):
        return config_filepath


def scrape_palette(palette_node):
    '''
    1. collection/palette .xgen file
    2. The entire collection/palette directory
    3. each Description's paths (including objects/modules, etc



    collection.name=testCollection
    collection.parent=
    collection.xgDataPath=${PROJECT}xgen/collections/testCollection
    collection.xgProjectPath=/home/bobby/maya/projects/xgen_testing/
    collection.xgDogTag=
    descriptions: ('testdescription', 'description', 'description2')

    '''
    paths = []

    palette_name = get_pallete_attr(palette_node, "name")
    logger.debug('Scraping dependencies for xgen palette "%s"', palette_name)
    palette_filename = cmds.getAttr("%s.xgFileName" % palette_node)
    logger.debug('Found palette filename: "%s"', palette_filename)
    palette_dirpath = os.path.dirname(cmds.file(q=True, sceneName=True))
    palette_filepath = os.path.join(palette_dirpath, palette_filename)
    logger.debug('Resolved palette filepath to: "%s"', palette_filepath)

    patch_filepath = os.path.splitext(palette_filepath)[0] + ".abc"
    logger.debug('patch_filepath: "%s"', patch_filepath)
    if os.path.isfile(patch_filepath):
        paths.append(patch_filepath)
    else:
        logger.warning("Expected patch file not found: %s", patch_filepath)

    paths.append(palette_filepath)

    palette_path = xgenm.palettePath(palette_name)
    logger.debug("palette_path:%s", palette_path)
    paths.append(palette_path)

    search_paths = get_search_paths(palette_name)
    paths.extend(search_paths)
    path_variables = get_path_variables(palette_name)
    paths = resolve_paths(paths, path_variables, search_paths, strict=True)

    for description_name in xgenm.descriptions(palette_name):
        logger.debug("Scraping dependencies for xgen Description: %s.%s", palette_name, description_name)
        description_paths = scrape_description(palette_name, description_name)
        logger.debug("description_paths: %s", description_paths)
        path_variables = get_path_variables(palette_name)
        desc_paths = get_desc_paths(palette_name, description_name)
        description_paths = resolve_paths(description_paths, path_variables, search_paths, desc_paths, strict=True)
        paths.extend(description_paths)

    return paths


def scrape_description(palette_name, description_name):
    '''
    description.name=BarfDescription
    description.flipNormals=false
    description.strayPercentage=0.0
    description.lodFlag=false
    description.averageWidth=1.0
    description.pixelCullSize=0.0
    description.pixelFadeSize=20.0
    description.cullFade=0.1
    description.minDensity=0.01
    description.cullWidthRatio=0.01
    description.maxWidthRatio=20.0
    description.groom=
    description.descriptionId=4

    objects: ('RendermanRenderer', 'SplinePrimitive', 'RandomGenerator', 'GLRenderer')


    '''
    paths = []

    for object_name in xgenm.objects(palette_name, description_name):
        logger.debug("Scraping dependencies for xgen object: %s.%s.%s", palette_name, description_name, object_name)
        object_paths = scrape_object(palette_name, description_name, object_name)
        logger.debug("object_paths: %s", object_paths)
        paths.extend(object_paths)

    return paths


def scrape_object(palette_name, description_name, object_name):
    scraper_class = MODULE_SCRAPERS.get(object_name, ModuleScraper)
    scraper = scraper_class(palette_name, description_name, object_name)
    return scraper.scrape(palette_name, description_name, object_name)


def scrape_archive():
    pass


def get_pallete_attr(palette_name, attr_name):
    return get_xgen_attr(attr_name, palette_name)


def get_description_attr(palette_name, description_name, attr_name):
    return get_xgen_attr(attr_name, palette_name, description_name)


def get_object_attr(palette_name, description_name, object_name, attr_name):
    return get_xgen_attr(attr_name, palette_name, description_name, object_name)


def get_xgen_attr(attr_name, palette_name, description_name="", object_name=""):
    return xgenm.getAttr(attr_name, palette_name, description_name, object_name)


def get_palette_data(palette_name):
    return get_data(palette_name)


def get_description_data(palette_name, description_name):
    return get_data(palette_name, description_name)


def get_object_data(palette_name, description_name, object_name):
    return get_data(palette_name, description_name, object_name)


def get_data(*args):
    data = {}
    for attr_name in xgenm.allAttrs(*args):
        data[attr_name] = xgenm.getAttr(attr_name, *args)
    return data


def resolve_paths(paths, variables, search_paths=(), desc_paths=(), strict=True, omit_missing=False):
    resolved_paths = []
    for path in paths:
        resolved_path = resolve_path(path, variables, search_paths, desc_paths, strict=strict, omit_missing=omit_missing)
        resolved_paths.append(resolved_path)
    return filter(None, resolved_paths)


def resolve_path(path, variables, search_paths=(), desc_paths=(), strict=True, omit_missing=False):
    '''
    Resolving paths:

    environment variables

    xgen variables
        ${PROJECT}
        ${DESC}
        User: ${HOME}/xgen
        Local: ${XGEN_ROOT}

    relative paths:
        xgDataPath (multiple paths)
        xgenm.userRepo()
        xgenm.localRepo()


    examples:
        '/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz'
        '${DESC}/guides.abc'
        '${PROJECT}xgen/collections/testCollection'
        '/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz'


    search_paths: list of str.


    '''
    # First subsitute any known variables
    if "${" in path:
        rx = re.compile("(%s)" % "|".join([re.escape(key) for key in variables.keys()]))
        path = rx.sub(lambda mo: variables[mo.string[mo.start():mo.end()]], path)

    print "path", path

    if "${DESC}" in path:
        for desc_path in desc_paths:
            resolved_path = path.replace("${DESC}", desc_path)
            print "resolved_path", resolved_path

            if os.path.exists(resolved_path):
                path = resolved_path
                break

            elif not os.path.isabs(resolved_path):
                abs_path = _resolve_relative_path(resolved_path, search_paths)
                if abs_path:
                    path = abs_path
                    break

    if not os.path.isabs(path):
        path = _resolve_relative_path(path, search_paths) or path

    if not os.path.exists(path):
        logger.debug("Path does not exist: %s", path)
        if strict:
            raise Exception("Path does not exist: %s" % path)

        if omit_missing:
            return

    return path


def _resolve_relative_path(path, search_paths):
    for search_path in search_paths:
        fullpath = os.path.join(search_path, path)
        if os.path.exists(fullpath):
            return fullpath


def get_data_paths(palette_name):
    data_paths = get_pallete_attr(palette_name, "xgDataPath") or ""
    logger.debug("data_paths_raw: %s", data_paths)
    data_paths = [path for path in data_paths.split(";") if path.strip()]
    path_variables = get_path_variables(palette_name)
    data_paths = resolve_paths(data_paths, path_variables, strict=True)
    logger.debug("data_paths_resolved %s", data_paths)
    return data_paths


def get_desc_paths(palette_name, description_name):
    '''
    ${DESC}
    variables["${DESC}"] = xgenm.descriptionPath(palette_name, description_name)
    '''
    data_paths = get_data_paths(palette_name)
    desc_paths = [os.path.join(path, description_name) for path in data_paths]
    desc_paths.append(xgenm.descriptionPath(palette_name, description_name))
    return desc_paths


def get_path_variables(palette_name):
    '''
    ${PROJECT}
    ${DESC}
    User: ${HOME}/xgen
    Local: ${XGEN_ROOT}
    Global: ${XGEN_LOCATION}
    '''
    variables = {}
    variables["${HOME}"] = xgenm.userRepo()
    variables["${XGEN_ROOT}"] = xgenm.localRepo()
    variables["${XGEN_LOCATION}"] = xgenm.globalRepo()
    variables["${PROJECT}"] = xgenm.getProjectPath()
    variables["${FRAME}"] = "#"
    print "variables", variables
    return variables


def get_search_paths(palette_name):
    '''
    xgDataPath (multiple paths)
    xgenm.userRepo()
    xgenm.localRepo()
    xgenm.globalRepo() # OMIT THIS BECAUSE PART OF INSTALLATION
    '''
    search_paths = []
    data_paths = get_pallete_attr(palette_name, "xgDataPath") or ""
    logger.debug("xgDataPath: %s", data_paths)
    search_paths.extend([path for path in data_paths.split(";") if path.strip()])
    search_paths.extend([xgenm.userRepo(), xgenm.localRepo()])
    return search_paths


class XgenScraper(object):
    pass


class ModuleScraper(object):
    '''

    xgenm.availableModules()

    ### FXModule ###
    AnimWiresFXModule
    BakedGroomManagerFXModule
    BlockAnimFXModule
    ClumpingFXModule
    CoilFXModule
    CollisionFXModule
    ControlWiresFXModule
    CutFXModule
    DebugFXModule
    ForceFXModule
        ApplyNetForceFXModule
        DirectionalForceFXModule
        PlaneForceFXModule
        PolylineForceFXModule
        SphereForceFXModule
    MeshCutFXModule
    NoiseFXModule
    ParticleFXModule
    PlaneAnimFXModule
    PreserveClumpsFXModule
    SnapshotFXModule
    WindFXModule

    ### Renderer ###
    FileRenderer
    GeometryRenderer
    GLRenderer
    GuideRenderer
    MelRenderer
    NullRenderer
    ParticleRenderer
    PointRenderer
    PromoteRenderer
    RendermanRenderer

    ### Generator ###
    FileGenerator
    GuideGenerator
    PointGenerator
    RandomGenerator
    UniformGenerator

    ### Primitive ###
    ArchivePrimitive
    CardPrimitive
    SpherePrimitive
    SplinePrimitive

    ### Patch ###
    NurbsPatch
    SubdPatch
    '''

    MODULE_NAME = None

    def __init__(self, palette_name, description_name, object_name, path_variables=None, search_paths=(), desc_paths=()):
        self.palette_name = palette_name
        self.description_name = description_name
        self.object_name = object_name
        self.path_variables = path_variables or get_path_variables(palette_name)
        self.search_paths = search_paths or get_search_paths(palette_name)
        self.desc_paths = desc_paths or get_desc_paths(palette_name, description_name)

    def scrape(self, palette_name, description_name, object_name):
        '''
        Return a list of paths.  These may be file paths or directory paths
        '''
        return []

    def resolve_path(self, path, strict=True, omit_missing=False):
        return resolve_path(path,
                            self.path_variables,
                            search_paths=self.search_paths,
                            desc_paths=self.desc_paths,
                            strict=strict,
                            omit_missing=omit_missing)

    def resolve_paths(self, paths, strict=True, omit_missing=False):
        return resolve_paths(paths,
                             self.path_variables,
                             search_paths=self.search_paths,
                             desc_paths=self.desc_paths,
                             strict=strict,
                             omit_missing=omit_missing)


class PrimitiveScraper(ModuleScraper):
    '''
    Primitive.cacheFileName=${DESC}/guides.abc
    Primitive.useCache=false
    Primitive.regionMap=${DESC}/Region/pillow
    Primitive.regionMask=0.0
    '''

    def scrape(self, palette_name, description_name, object_name):
        paths = super(PrimitiveScraper, self).scrape(palette_name, description_name, object_name)
        cache_paths = self.scrape_cache(palette_name, description_name, object_name)
        logger.debug("cache_paths: %s", cache_paths)
        region_map_paths = self.scrape_region_map(palette_name, description_name, object_name)
        logger.debug("region_map_paths: %s", region_map_paths)
        return paths + cache_paths + region_map_paths

    def scrape_cache(self, palette_name, description_name, object_name):
        '''
        Primitive.useCache=true
        Primitive.cacheFileName=${DESC}/guides.abc
        '''
        paths = []
        use_cache = get_object_attr(palette_name, description_name, object_name, "useCache") or ""
        logger.debug("use_cache: %s", use_cache)
        if str_to_bool(use_cache):
            cache_filepath = get_object_attr(palette_name, description_name, object_name, "cacheFileName")
            logger.debug("cache_filepath: %s", cache_filepath)
            paths.append(cache_filepath)
        return paths

    def scrape_region_map(self, palette_name, description_name, object_name):
        '''
        regionMap=${DESC}/Region/pillow
        SplinePrimitive.regionMask=0.0
        '''
        paths = []
        region_map_path = get_object_attr(palette_name, description_name, object_name, "regionMap") or ""
        logger.debug("region_map_path: %s", region_map_path)
        if region_map_path.strip():
            paths.append(region_map_path)
        return self.resolve_paths(paths, strict=False, omit_missing=True)


class SplinePrimitiveScraper(PrimitiveScraper):
    '''
    SplinePrimitive._patchNames=
    SplinePrimitive._wireNames=
    SplinePrimitive.aboutN=$a=0.0000;#-180.0,180.0\n$a
    SplinePrimitive.attrCVCount=3
    SplinePrimitive.bendParam[0]=$a=0.5000;#0.0,1.0\n$a
    SplinePrimitive.bendU[0]=$a=0.0000;#-2.0,2.0\n$a
    SplinePrimitive.bendV[0]=$a=0.0000;#-2.0,2.0\n$a
    SplinePrimitive.cacheFileName=${DESC}/guides.abc
    SplinePrimitive.cutParam=1.0
    SplinePrimitive.CVFrequency=1.0
    SplinePrimitive.depth=$a=1.0;#0.05,5.0\n$a
    SplinePrimitive.displayWidth=true
    SplinePrimitive.faceCamera=true
    SplinePrimitive.fxCVCount=5
    SplinePrimitive.guideMask=1.0
    SplinePrimitive.guideSpacing=1.0
    SplinePrimitive.iMethod=0
    SplinePrimitive.length=$a=1.0000;#0.05,5.0\n$a
    SplinePrimitive.liveMode=false
    SplinePrimitive.offN=$a=0.0000;#-180.0,180.0\n$a
    SplinePrimitive.offU=$a=0.0000;#-2.0,2.0\n$a
    SplinePrimitive.offV=$a=0.0000;#-2.0,2.0\n$a
    SplinePrimitive.regionMap=${DESC}/Region/pillows
    SplinePrimitive.regionMask=0.0
    SplinePrimitive.taper=$a=0.0000;#-1.0,1.0\n$a
    SplinePrimitive.taperStart=$a=0.0000;#0.0,1.0\n$a
    SplinePrimitive.texelsPerUnit=10.0
    SplinePrimitive.tubes=
    SplinePrimitive.tubeShade=true
    SplinePrimitive.uniformCVs=true
    SplinePrimitive.useCache=false
    SplinePrimitive.width=$a=0.1000;#0.005,0.5\n$a
    SplinePrimitive.widthRamp=rampUI(0.0,1.0,1:0.360927152318,0.197368421053,1:1.0,1.0,1)
    '''

    MODULE_NAME = "SplinePrimitive"


class SpherePrimitiveScraper(PrimitiveScraper):
    '''
    SpherePrimitive._patchNames=
    SpherePrimitive._wireNames=
    SpherePrimitive.aboutN=$a=0.0000;#-180.0,180.0\n$a
    SpherePrimitive.cacheFileName=/usr/share/DOWNLOADS/vesalius/2018_01_31b/MARIOSIMTEST/animation/fth_tr015_anim_frd_v016.abc
    SpherePrimitive.depth=$a=1.0000;#0.05,5.0\n$a
    SpherePrimitive.iMethod=1
    SpherePrimitive.length=$a=1.0000;#0.05,5.0\n$a
    SpherePrimitive.liveMode=false
    SpherePrimitive.offN=$a=0.0000;#-180.0,180.0\n$a
    SpherePrimitive.offU=$a=0.0000;#-2.0,2.0\n$a
    SpherePrimitive.offV=$a=0.0000;#-2.0,2.0\n$a
    SpherePrimitive.regionMap=${DESC}/Region/
    SpherePrimitive.regionMask=0.0
    SpherePrimitive.twist=$a=0.0000;#-180.0,180.0\n$a
    SpherePrimitive.useCache=true
    SpherePrimitive.width=$a=0.1000;#0.005,0.5\n$a
    '''

    MODULE_NAME = "SpherePrimitive"


class ArchivePrimitiveScraper(PrimitiveScraper):
    '''
    ArchivePrimitive._patchNames=
    ArchivePrimitive._wireNames=
    ArchivePrimitive.aboutN=$a=0.0000;#-180.0,180.0\n$a
    ArchivePrimitive.aCount=2
    ArchivePrimitive.aIndex=pick(rand(),0,$aCount-1)
    ArchivePrimitive.aLOD=$lowDistance=30.0000;#0.0,50.0\n$mediumDistance=10.0000;#0.0,50.0\nd=length(cam-P);\nret=0;\nif( d>$lowDistance ){ret=2;}\nelse if( d>$mediumDistance ){ret=1;}\nret\n
    ArchivePrimitive.archive__aColor[0]=[1.0,0.0,0.0]
    ArchivePrimitive.archive__aColor[1]=[1.0,0.0,0.0]
    ArchivePrimitive.archiveSize=1.0
    ArchivePrimitive.cacheFileName=${DESC}/guides.abc
    ArchivePrimitive.depth=$a=1.0000;#0.05,5.0\n$a
    ArchivePrimitive.files=#ArchiveGroup 0 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/maya/projects/xgen_testing/xgen/archives/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n1 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n2 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n3 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n4 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n5 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n\n#ArchiveGroup 1 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/xgen/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n1 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n2 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n3 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n4 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n5 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n\n
    ArchivePrimitive.frame=$a=0;#0,100\n$a
    ArchivePrimitive.hiIndex=$aIndex*$aMul + 0 + 3
    ArchivePrimitive.iMethod=0
    ArchivePrimitive.length=$a=1.0000;#0.05,5.0\n$a
    ArchivePrimitive.liveMode=true
    ArchivePrimitive.lodHiLower=62500
    ArchivePrimitive.lodHiUpper=160000
    ArchivePrimitive.lodLoLower=0
    ArchivePrimitive.lodLoUpper=2500
    ArchivePrimitive.lodMedLower=10000
    ArchivePrimitive.lodMedUpper=40000
    ArchivePrimitive.loIndex=$aIndex*$aMul + 2 + 3
    ArchivePrimitive.medIndex=$aIndex*$aMul + 1 + 3
    ArchivePrimitive.offN=$a=0.0000;#-180.0,180.0\n$a
    ArchivePrimitive.offU=$a=0.0000;#-2.0,2.0\n$a
    ArchivePrimitive.offV=$a=0.0000;#-2.0,2.0\n$a
    ArchivePrimitive.proxyIndex=$aIndex*$aMul + $aLOD
    ArchivePrimitive.regionMap=${DESC}/Region/
    ArchivePrimitive.regionMask=0.0
    ArchivePrimitive.twist=$a=0.0000;#-180.0,180.0\n$a
    ArchivePrimitive.useCache=false
    ArchivePrimitive.width=$a=1.0000;#0.05,5.0\n$a
    '''

    MODULE_NAME = "ArchivePrimitive"

    def scrape(self, palette_name, description_name, object_name):
        paths = super(ArchivePrimitiveScraper, self).scrape(palette_name, description_name, object_name)
        files_paths = self.scrape_files_paths(palette_name, description_name, object_name)
        logger.debug("files_paths: %s", files_paths)
        return paths + files_paths

    def scrape_files_paths(self, palette_name, description_name, object_name):
        '''
        ArchivePrimitive.files=#ArchiveGroup 0 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/maya/projects/xgen_testing/xgen/archives/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n1 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n2 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n3 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n4 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n5 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n\n#ArchiveGroup 1 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/xgen/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n1 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n2 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n3 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n4 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n5 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n\n
        '''
        paths = []
        files = get_object_attr(palette_name, description_name, object_name, "files") or ""
        logger.debug("files: %s", files)
        if files.strip():
            for archive_group in self._parse_files_str(files):
                logger.debug("archive_group: %s", archive_group)
                archive_paths = self._scrape_archive_group(archive_group)
                paths.extend(archive_paths)

        return paths

    def _parse_files_str(self, files_str):
        '''
        Parse the "files" string into dictioary of data.

        example str: 
            ' #ArchiveGroup 0 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/maya/projects/xgen_testing/xgen/archives/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n1 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n2 "/tmp/maya/projects/xgen_testing/xgen/archives/abc/cat_archive.abc" material=cat_archive:blinn1SG objects=|pCube1\n3 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n4 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n5 "/tmp/maya/projects/xgen_testing/xgen/archives/ass/cat_archive__pCube1.${FRAME}.ass.gz" material=cat_archive:blinn1 objects=|pCube1\n\n#ArchiveGroup 1 name="cat_archive" thumbnail="cat_archive.png" description="No description." materials="/tmp/xgen/materials/cat_archive.ma" color=[1.0,0.0,0.0]\n0 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n1 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n2 "/tmp/xgen/abc/cat_archive.abc" material=cat_archive:purple_box:blinn1SG objects=|purple_box:pCube1\n3 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n4 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n5 "/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz" material=cat_archive:purple_box:blinn1 objects=|purple_box:pCube1\n\n' 

        example result dict:


         {'0': '/tmp/xgen/abc/cat_archive.abc',
          '1': '/tmp/xgen/abc/cat_archive.abc',
          '2': '/tmp/xgen/abc/cat_archive.abc',
          '3': '/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz',
          '4': '/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz',
          '5': '/tmp/xgen/ass/cat_archive__purple_box_pCube1.${FRAME}.ass.gz',
          'ArchiveGroup': '1',
          'color': '[1.0,0.0,0.0]',
          'description': 'No description.',
          'material': 'cat_archive:purple_box:blinn1',
          'materials': '/tmp/xgen/materials/cat_archive.ma',
          'name': 'cat_archive',
          'objects': '|purple_box:pCube1',
          'thumbnail': 'cat_archive.png'}

        '''
        archive_groups = []
        files_str = xgenm.prepForEditor(files_str)
        for raw_values in filter(None, files_str.split("#")):

            postional_values = []
            group_data = {}
            for raw_value in shlex.split(raw_values):
                if "=" in raw_value:
                    key, value = raw_value.split("=", 1)
                    group_data[key] = value
                else:
                    postional_values.append(raw_value)
            positional_dict = dict(itertools.izip_longest(*[iter(postional_values)] * 2, fillvalue=""))
            group_data.update(positional_dict)
            archive_groups.append(group_data)

        return archive_groups

    @classmethod
    def _scrape_archive_group(cls, archive_group):
        '''
        Pick apart the archive_group dictionary for any relevant path data
        '''
        paths = [archive_group["materials"]]
        for key, value in archive_group.iteritems():
            if key.isdigit():
                paths.append(value)
        return paths


class CardPrimitiveScraper(ModuleScraper):
    '''
    CardPrimitive._patchNames=
    CardPrimitive._wireNames=
    CardPrimitive.aboutN=$a=0.0000;#-180.0,180.0\n$a
    CardPrimitive.bendParamU=$a=0.5000;#0.0,1.0\n$a
    CardPrimitive.bendParamV=$a=0.5000;#0.0,1.0\n$a
    CardPrimitive.bendU=$a=0.0000;#-2.0,2.0\n$a
    CardPrimitive.bendV=$a=0.0000;#-2.0,2.0\n$a
    CardPrimitive.cacheFileName=${DESC}/guides.abc
    CardPrimitive.depth=$a=1.0;#0.05,5.0\n$a
    CardPrimitive.faceCamera=false
    CardPrimitive.iMethod=1
    CardPrimitive.length=$a=1.0000;#0.05,5.0\n$a
    CardPrimitive.liveMode=false
    CardPrimitive.offN=$a=0.0000;#-180.0,180.0\n$a
    CardPrimitive.offU=$a=0.0000;#-2.0,2.0\n$a
    CardPrimitive.offV=$a=0.0000;#-2.0,2.0\n$a
    CardPrimitive.regionMap=${DESC}/Region/
    CardPrimitive.regionMask=0.0
    CardPrimitive.twist=$a=0.0000;#-180.0,180.0\n$a
    CardPrimitive.useCache=true
    CardPrimitive.width=$a=1.0000;#0.05,5.0\n$a
    '''

    MODULE_NAME = "CardPrimitive"


class RandomGeneratorScraper(ModuleScraper):
    '''
    RandomGenerator.bump=$a=0.0000;#-1.0,1.0\n$a
    RandomGenerator.cullAngleBF=0.0
    RandomGenerator.cullAngleF=0.0
    RandomGenerator.cullBackface=false
    RandomGenerator.cullExpr=$a=0.0000;#0.0,1.0\n$a
    RandomGenerator.cullFlag=false
    RandomGenerator.cullFrustrum=false
    RandomGenerator.dcFlag=false
    RandomGenerator.density=1.0
    RandomGenerator.displacement=$a=0.0000;#-1.0,1.0\n$a
        RandomGenerator.mask=1.0 # map('${DESC}/density/')
    RandomGenerator.offset=$a=0.0000;#-1.0,1.0\n$a
        RandomGenerator.pointDir=${DESC}/Points/
    RandomGenerator.ptLength=1.0
    RandomGenerator.scFlag=true
    RandomGenerator.usePoints=false
    RandomGenerator.vectorDisplacement=0
    '''

    MODULE_NAME = "RandomGenerator"


MODULE_SCRAPERS = dict([(scraper.MODULE_NAME, scraper) for scraper in [
    SplinePrimitiveScraper,
    SpherePrimitiveScraper,
    ArchivePrimitiveScraper,
]])
