from krita import *
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import re
import math
from distutils.dir_util import copy_tree
import csv
import json
import html

KI = Krita.instance()
resource_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
try:
    resource_path = KI.readSetting("", "Resource Folder", resource_path)
except:
    pass
plugin_path = os.path.join(resource_path, "pykrita/noita_editor")

noita_data_path = os.path.join(os.getenv("appdata"), "../LocalLow/Nolla_Games_Noita")
noita_game_path = "C:/Program Files (x86)/Steam/steamapps/common/Noita"
noita_mods_path = os.path.join(noita_game_path, "mods")

info = InfoObject()
info.setProperty("alpha", True)
info.setProperty("compression", 9)
info.setProperty("forceSRGB", False)
info.setProperty("indexed", False)
info.setProperty("interlaced", False)
info.setProperty("saveSRGBProfile", False)
info.setProperty("transparencyFillcolor", [0,0,0])

custom_biome_xml = """
<Biome>
  <Topology
    name="_EMPTY_"
    background_image=""
    background_use_neighbor="0"

    lua_script="mods/{0}/files/biome.lua"
    limit_background_image="0"
    coarse_map_force_terrain="1"
    pixel_scene="1"
    noise_biome_edges="0">
  </Topology>

  <!------------ MATERIALS -------------------->
  {materials}
</Biome>
"""

custom_biome_lua = """
-- default biome functions that get called if we can't find a a specific biome that works for us
CHEST_LEVEL = 3
dofile_once("data/scripts/director_helpers.lua")
dofile( "data/scripts/biome_scripts.lua" )
dofile( "data/scripts/items/generate_shop_item.lua" )
dofile( "data/scripts/perks/perk.lua" )
dofile("data/scripts/gun/procedural/gun_action_utils.lua")

RegisterSpawnFunction( 0xffffeedd, "init" )

function init( x, y, w, h )
        file_suffix = "_"..(x-{x_offset}).."_"..y..".png"
        LoadPixelScene("mods/{0}/files/biome_impl/materials"..file_suffix, "mods/{0}/files/biome_impl/colors"..file_suffix, x, y, "mods/{0}/files/biome_impl/background"..file_suffix, true)
end
"""

init_lua = """
local nxml = dofile_once("mods/{0}/files/lib/nxml.lua")

local biomes_all = ModTextFileGetContent("data/biome/_biomes_all.xml")
local biomes_xml = nxml.parse(biomes_all)

biomes_xml.attr.biome_offset_y="0"
biomes_xml:add_child(nxml.new_element("Biome", {{biome_filename="mods/{0}/files/biome.xml", height_index="0", color="ff012345"}}))

ModTextFileSetContent("data/biome/_biomes_all.xml", nxml.tostring(biomes_xml))

local magic_numbers = ModTextFileGetContent("data/magic_numbers.xml")
local magic_numbers_xml = nxml.parse(magic_numbers)
magic_numbers_xml.attr.DESIGN_PLAYER_START_POS_X = "{start_x}"
magic_numbers_xml.attr.DESIGN_PLAYER_START_POS_Y = "{start_y}"
ModTextFileSetContent("data/magic_numbers.xml", nxml.tostring(magic_numbers_xml))
"""

pixel_scenes_xml = """
<PixelScenes>
</PixelScenes>
"""

mod_xml = """
<Mod
    name="{0}"
    description="{1}"
    request_no_api_restrictions="0"
>
</Mod>
"""

biome_lua_entity_append = """
RegisterSpawnFunction(0x{0}, "spawn_entity_{0}")
function spawn_entity_{0}(x, y)
{1}
end
"""

entity_svg_template = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<g>
<text transform="matrix(0,0,0,0,0,0)">{info}</text>
<image xlink:href="data:image/png;base64,{data}" x="0" y="0" width="{width}" height="{height}" shape-rendering="crispEdges"/>
</g>
</svg>"""

# def refresh_entities():
#     doc = KI.activeDocument()
#     def find_entities(layer, position):
#         position = position+layer.position()
#         if(layer.type() == "vectorlayer"):
#             for shape in layer.shapes():
#                 shape_svg = shape.toSvg()
#                 info_match = re.search(r'Entity:(.*?),x:([\d.]*),y:([\d.]*)', shape_svg)
#                 if(info_match):
#                     info_text = info_match.group(0)
#                     print("found "+info_text)
#                     print()
#                     image = re.search(r'data:image/png;base64,(.*)"', shape_svg).group(1)
#                     width = re.search(r'<image.*width="(.*?)"', shape_svg).group(1)
#                     height = re.search(r'<image.*height="(.*?)"', shape_svg).group(1)
#                     entity_svg = entity_svg_template.format(info=info_text, data=image, width=width, height=height)
#                     new_shape = layer.addShapesFromSvg(entity_svg)[0]
#                     #new_shape.setTransformation(shape.transformation())
#                     new_shape.setPosition(shape.position())
#                     print(shape.transformation().m11())
#                     print()
#                     shape.remove()
#         for child in layer.childNodes():
#             find_entities(child, position)
#     find_entities(doc.rootNode(), QPoint(0,0))

ingame_strings = {"mat_air": "test"}
language_id = 0
language_list = None
def load_ingame_strings():
    global ingame_strings
    global language_id
    global language_list

    common_csv = os.path.join(noita_game_path, "data/translations/common.csv")
    language_list = None
    with open(common_csv, "r", encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if(not language_list):
                language_list = row[1:]
                continue
            ingame_strings[row[0]] = row[1:]

    config_xml = ET.parse(os.path.join(noita_data_path, "save_shared/config.xml"))
    language = config_xml.getroot().attrib["language"]
    for i,l in enumerate(language_list):
        if(l == language):
            language_id = i
            break

try:
    load_ingame_strings()
except:
    pass

def get_ingame_string(str):
    if(len(str) > 1 and str[0] == '$' and str[1:] in ingame_strings):
        return ingame_strings[str[1:]][language_id]
    return str

def get_entity_info(svg_str):
    info_match = re.search(r'<text.*?>(.*?)</text>', svg_str)
    return json.loads(html.unescape(info_match.group(1))) if info_match else info_match

def get_entity_script(data, map_name):
    filename = data["filename"]
    processed_filename = filename.replace('<mod_name>', map_name)
    script = 'EntityLoad("{}", x, y)'.format(processed_filename)
    if(filename=="script"):
        script = data["script"]
    if(filename=="spawn_perk"):
        script = 'perk_spawn(x,y,"{}",{})'.format(data["perk_id"].strip(), "false" if data["remove_other_perks"] else "true")
    if(filename=="spawn_card"):
        script = 'CreateItemActionEntity("{}",x,y)'.format(data["action_id"].strip())
    if(filename=="spawn_wand"):
        script = """
local wand = EntityLoad("{}",x,y)
for i,child in ipairs(EntityGetAllChildren(wand) or {{}}) do
EntityKill(child)
end
""".format(data["wand_file"].strip().replace('\\', '/'))
        for action in data["ac_actions"].split(','):
            action = action.strip()
            if(not action):
                continue
            script += '\nAddGunActionPermanent(wand,"{}")'.format(action)
        for action in data["actions"].split(','):
            action = action.strip()
            if(not action):
                continue
            script += '\nAddGunAction(wand,"{}")'.format(action)
    if(filename=="spawn_flask"):
        script = 'local potion = EntityLoad("data/entities/items/pickup/potion_empty.xml",x,y)'
        for material, amount in zip(data["material_names"].split(','), data["material_amounts"].split(',')):
            material = material.strip()
            amount = amount.strip()
            if(not material):
                continue
            script += '\nAddMaterialInventoryMaterial(potion,"{}",{})'.format(material,amount)
    if(filename=="portal"):
        script = """
local portal = EntityLoad("data/entities/buildings/teleport.xml",x,y)
local teleport_comp = EntityGetFirstComponentIncludingDisabled(portal, "TeleportComponent")
ComponentSetValue2(teleport_comp, "target", {}, {})
ComponentSetValue2(teleport_comp, "target_x_is_absolute_position", {})
ComponentSetValue2(teleport_comp, "target_y_is_absolute_position", {})
""".format(data["target_x"].strip(),
           data["target_y"].strip(),
           "true" if data["target_x_is_absolute_position"] else "false",
           "true" if data["target_y_is_absolute_position"] else "false")
    if(filename=="other_entity"):
        script = 'EntityLoad("{}",x,y)'.format(data["other_filename"].strip().replace('\\', '/'))
    return script

def find_selected_entity_info(layer):
    if(layer.type() == "vectorlayer"):
        for shape in layer.shapes():
            data = get_entity_info(shape.toSvg())
            if(shape.isSelected() and data):
                return data, shape, layer
    for child in layer.childNodes():
        out = find_selected_entity_info(child)
        if(out):
            return out
    return None

def unblur_entities(ppi, layer, position=QPoint(0,0)):
    position = position+layer.position()
    if(layer.type() == "vectorlayer"):
        for shape in layer.shapes():
            data = get_entity_info(shape.toSvg())
            if(data):
                transform = shape.transformation()
                shape.setTransformation(QTransform(72/ppi, 0, 0, 72/ppi, transform.dx(), transform.dy()))
                # shape.update()
    for child in layer.childNodes():
        unblur_entities(ppi, child, position)

def export_map():
    doc = KI.activeDocument()
    KI.setBatchmode(True)
    ppi = doc.resolution()

    work_dir, map_name = os.path.split(doc.fileName())
    map_name = os.path.splitext(map_name)[0]
    map_dir = os.path.join(noita_mods_path, map_name)

    mod_files_dir = os.path.join(work_dir, "mod_files")
    if(not os.path.isdir(mod_files_dir)):
        os.makedirs(mod_files_dir)
        [os.path.join(map_dir, "mod.xml")     , mod_xml],
    mod_xml_filename = os.path.join(mod_files_dir, "mod.xml")
    if(os.path.isfile(mod_xml_filename)):
        mod_xml_tree = ET.parse(mod_xml_filename)
        root = mod_xml_tree.getroot()
        map_user_name = root.attrib["name"]
        map_description = root.attrib["description"]
    else:
        map_user_name = map_name
        map_description = "A custom map."
        mod_xml_tree = ET.fromstring(mod_xml.format(map_user_name, map_description))

    save_dialogue = QDialog()
    save_dialogue.setLayout(QVBoxLayout())

    #Export location line
    map_dir_line = QHBoxLayout()
    save_dialogue.layout().addLayout(map_dir_line)

    map_dir_line.addWidget(QLabel("Export Folder: "))
    map_dir_edit = QLineEdit(map_dir)
    map_dir_line.addWidget(map_dir_edit)

    browse_button = QPushButton("Browse")
    map_dir_line.addWidget(browse_button)
    def browse_mod_dir():
        nonlocal map_dir_edit
        map_dir = map_dir_edit.text()
        map_dir = QFileDialog.getExistingDirectory(None, "Select Export Folder", map_dir)
        map_dir_edit.setText(map_dir)
    browse_button.clicked.connect(browse_mod_dir)

    #Mod Name Line
    map_name_line = QHBoxLayout()
    save_dialogue.layout().addLayout(map_name_line)
    save_dialogue.resize(700,400)

    map_name_line.addWidget(QLabel("Map Name: "))
    map_name_edit = QLineEdit(map_name)
    map_name_line.addWidget(map_name_edit)

    #Description Line
    save_dialogue.layout().addWidget(QLabel("Description:"))
    map_description_edit = QTextEdit(map_description)
    save_dialogue.layout().addWidget(map_description_edit, 1)

    #Export Button
    accept_reject_line = QHBoxLayout()
    save_dialogue.layout().addLayout(accept_reject_line)
    export_button = QPushButton("Export")
    export_button.clicked.connect(save_dialogue.accept)
    accept_reject_line.addWidget(export_button)

    cancel_button = QPushButton("Cancel")
    cancel_button.clicked.connect(save_dialogue.reject)
    accept_reject_line.addWidget(cancel_button)

    ################# Execute and wait for dialogue ##################
    if(save_dialogue.exec() != QDialog.Accepted):
        return

    wait_dialogue = QDialog()
    wait_dialogue.setLayout(QVBoxLayout())
    wait_dialogue.layout().addWidget(QLabel("Exporting, please wait"))
    export_status = QLabel("saving entities...")
    export_status.setAlignment(Qt.AlignHCenter)
    wait_dialogue.layout().addWidget(export_status)
    wait_dialogue.open()

    map_dir = map_dir_edit.text()
    map_name = os.path.split(map_dir)[1]
    map_user_name = map_name_edit.text()
    map_description = map_description_edit.toPlainText()

    mod_xml_tree.getroot().set("name", map_name)
    mod_xml_tree.getroot().set("description", map_description)
    mod_xml_tree.write(mod_xml_filename)

    export_dir = os.path.join(map_dir, "files/biome_impl")

    os.makedirs(export_dir, exist_ok=True)

    export_layers = {"materials", "colors", "background"}

    entities = []
    entity_colors = {}

    current_color = 0xFFFFFFFD

    biome_lua_append = ""

    spawn_x = 0
    spawn_y = 0

    def find_entities(layer, position):
        nonlocal entities
        nonlocal current_color
        nonlocal biome_lua_append
        nonlocal ppi
        nonlocal spawn_x
        nonlocal spawn_y
        nonlocal map_name
        position = position+layer.position()
        if(layer.type() == "vectorlayer"):
            for shape in layer.shapes():
                data = get_entity_info(shape.toSvg())
                if(data):
                    # filename = data_match.group(1).replace("\\", "/")
                    # offset_x = float(data_match.group(2))
                    # offset_y = float(data_match.group(3))
                    # extra_data = float(data_match.group(4))
                    filename = data['filename']
                    offset_x = data['x']
                    offset_y = data['y']

                    transform = shape.transformation()
                    pos = position+QPointF(transform.dx(), transform.dy())*(ppi/72)
                    x = int(pos.x()+offset_x)
                    y = int(pos.y()+offset_y)
                    if(filename == "spawn_marker"):
                        spawn_x = x
                        spawn_y = y
                        continue
                    script = get_entity_script(data, map_name)
                    entities.append((script, x, y))
                    if(script not in entity_colors):
                        entity_colors[script] = current_color.to_bytes(4, 'little')
                        color_string = "{:08x}".format(current_color)
                        biome_lua_append += biome_lua_entity_append.format(color_string, script)
                        current_color -= 1

        for child in layer.childNodes():
            find_entities(child, position)

    find_entities(doc.rootNode(), QPoint(0,0))

    materials_layer = doc.nodeByName("materials")
    entity_pixel_layer = None
    for child in materials_layer.childNodes():
        if(child.name() == "entity_pixels"):
            entity_pixel_layer = child
            break

    if(entity_pixel_layer == None):
        entity_pixel_layer = doc.createNode("entity_pixels", "paintlayer")
        materials_layer.addChildNode(entity_pixel_layer, None)

    if(entity_pixel_layer.colorDepth() != "U8" or len(entity_pixel_layer.channels()) != 4):
        raise ValueError("Document Color Space must be RGB/Alpha 8-Bit integer/channel")
    bytes_per_pixel = 4
    entity_pixel_array = QByteArray(doc.width()*doc.height()*bytes_per_pixel, b'\x00')

    for script, x, y in entities:
        if(0 <= x and x < doc.width() and 0 <= y and y < doc.height()):
            entity_pixel_array.replace((x+y*doc.width())*bytes_per_pixel, 4, entity_colors[script])

    entity_pixel_layer.setPixelData(entity_pixel_array, 0, 0, doc.width(), doc.height())
    doc.refreshProjection()
    entity_pixel_layer.setLocked(True)

    biome_map_w = (doc.width()+511)//512
    biome_map_h = (doc.height()+511)//512

    export_status.setText("exporting layers...")
    # for layer_name in export_layers:
    #     layer = doc.nodeByName(layer_name)
    #     for x in range(0, doc.width()-1, 512):
    #         for y in range(0, doc.height()-1, 512):
    #             filename = os.path.join(export_dir, "%s_%d_%d.png"%(layer.name(), x, y))
    #             success = layer.save(filename, ppi, ppi, info, QRect(x,y,512,512))
    for layer_name in export_layers:
        layer = doc.nodeByName(layer_name)
        filename = os.path.join(export_dir, "%s_full.png"%(layer.name()))
        success = layer.save(filename, ppi, ppi, info, QRect(0,0,biome_map_w*512,biome_map_w*512))
        image = QImage(filename)
        for x in range(0, doc.width()-1, 512):
            for y in range(0, doc.height()-1, 512):
                tile_filename = os.path.join(export_dir, "%s_%d_%d.png"%(layer.name(), x, y))
                image.copy(x,y,512,512).save(tile_filename)
        os.remove(filename)


    export_status.setText("creating biome map...")
    files_path = os.path.join(map_dir, "files/")
    data_biome_impl_path = os.path.join(map_dir, "data/biome_impl/")
    os.makedirs(data_biome_impl_path, exist_ok=True)

    biome_map_doc = KI.createDocument(biome_map_w, biome_map_h, "biome_map.png", "RGBA", "U8", "", 120.0)
    biome_map_doc.setBackgroundColor(QColor("#ff012345"))
    biome_map_doc.setBatchmode(True)
    biome_map_doc.exportImage(os.path.join(data_biome_impl_path, "biome_map.png"), info)
    biome_map_doc.close()

    export_status.setText("copying mod files...")
    lib_path = os.path.join(files_path, "lib")
    os.makedirs(lib_path, exist_ok=True)

    user_init_lua = ""
    user_init_lua_path = os.path.join(mod_files_dir, "init.lua")
    try:
        with open(user_init_lua_path, 'r') as file:
            user_init_lua = file.read()
    except:
        pass

    user_biome_materials_xml = """
  <Materials
    name="custom_map"
     >
   </Materials>
"""
    user_biome_materials_xml_path = os.path.join(work_dir, "biome_materials.xml")
    try:
        with open(user_biome_materials_xml_path, 'r') as file:
            user_biome_materials_xml = file.read()
    except:
        pass

    export_status.setText("copying nxml...")
    shutil.copyfile(os.path.join(plugin_path, "nxml.lua"), os.path.join(lib_path, "nxml.lua"))
    export_status.setText("copying mod_files...")
    copy_tree(mod_files_dir, map_dir)


    data_biome_path = os.path.join(map_dir, "data/biome")
    os.makedirs(data_biome_path, exist_ok=True)

    x_offset = int(biome_map_w//2)*512
    files_to_copy = [
        [os.path.join(data_biome_path, "_pixel_scenes.xml"), pixel_scenes_xml, {}, ""],
        [os.path.join(files_path, "biome.xml"), custom_biome_xml, {"materials": user_biome_materials_xml}, ""],
        [os.path.join(files_path, "biome.lua"), custom_biome_lua, {"x_offset":x_offset}, biome_lua_append],
        [os.path.join(map_dir, "init.lua")    , init_lua, {"start_x":spawn_x+x_offset, "start_y":spawn_y}, user_init_lua],
    ]
    for filename, contents, kwargs, appendix in files_to_copy:
        export_status.setText("copying {}...".format({filename}))
        with open(filename, 'w') as file:
            file.write(contents.format(map_name, **kwargs)+appendix)

    wait_dialogue.close()

class NoitaEditorDocker(DockWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Noita Editor")

        main_widget = QWidget(self)
        self.setWidget(main_widget)
        main_widget.setLayout(QVBoxLayout())

        # config_button = QPushButton("Map Settings", main_widget)
        # config_button.clicked.connect(config_map)
        # main_widget.layout().addWidget(config_button)

        def make_layers():
            doc = KI.activeDocument()
            if(doc):
                root_node = doc.rootNode()
                for layer_name in ["background", "materials", "colors"]:
                    if(doc.nodeByName(layer_name)):
                        continue
                    new_layer = doc.createGroupLayer(layer_name)
                    root_node.addChildNode(new_layer, None)
                    paint_layer = doc.createNode(layer_name+" 0", "paintlayer")
                    new_layer.addChildNode(paint_layer, None)

                layer_name = "entities 0"
                if(not doc.nodeByName(layer_name)):
                    new_layer = doc.createVectorLayer(layer_name)
                    root_node.addChildNode(new_layer, None)

        make_layers_button = QPushButton("Setup Layers", main_widget)
        make_layers_button.clicked.connect(make_layers)
        main_widget.layout().addWidget(make_layers_button)

        #TODO: background material settings

        export_button = QPushButton("Export Map", main_widget)
        export_button.clicked.connect(export_map)
        main_widget.layout().addWidget(export_button)

        main_widget.layout().addStretch(1)

    def canvasChanged(self, canvas):
        pass

class MaterialsDocker(DockWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Noita Material Picker")

        main_widget = QWidget(self)
        self.setWidget(main_widget)
        main_widget.setLayout(QVBoxLayout())

        materials_label_line = QHBoxLayout()
        materials_label_line.setContentsMargins(0,0,0,0)
        main_widget.layout().addLayout(materials_label_line)

        materials_label_line.addWidget(QLabel("Search:", main_widget))

        materials_search = QLineEdit(main_widget)
        materials_label_line.addWidget(materials_search)

        materials_box = QListWidget(main_widget)
        materials_box.setSizePolicy(QSizePolicy.Policy.Minimum,
                                    QSizePolicy.Policy.Minimum)
        materials_box.setViewMode(QListView.IconMode)
        materials_box.setUniformItemSizes(True)
        materials_box.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        materials_box.setResizeMode(QListView.ResizeMode.Adjust)
        materials_box.setMinimumHeight(30)
        materials_box.setMovement(QListView.Static)

        main_widget.layout().addWidget(materials_box, 1)

        materials = []
        materials_xml = ET.parse(os.path.join(plugin_path, "materials.xml"))
        for child in materials_xml.getroot():
            if(child.tag == "CellData" or child.tag == "CellDataChild"):
                materials.append(child.attrib)
        n_cols = 5
        for i, material in enumerate(materials):
            material_color = material["wang_color"]
            material_name = material["name"]
            material_ui_name = get_ingame_string(material["ui_name"]) if "ui_name" in material else material_name
            icon_pixmap = QPixmap(16,16)
            color = QColor("#"+material_color)
            icon_pixmap.fill(color)
            material_button = QListWidgetItem(QIcon(icon_pixmap), material_ui_name, materials_box)
            material_button.setSizeHint(QSize(32, 36))
            material_button.setTextAlignment(0x0024)
            material_button.setToolTip(material_ui_name+" ("+material_name+")")
            materials_box.addItem(material_button)

            material_button.setData(0x0100, QVariant(material))

        def set_material_color(item):
            material = item.data(0x0100)
            color = ManagedColor.fromQColor(QColor("#"+material["wang_color"]))
            KI.activeWindow().activeView().setForeGroundColor(color)

        materials_box.itemClicked.connect(set_material_color)

        def search_materials(text):
            nonlocal materials_box
            text = text.lower()
            for child in materials_box.findItems("", Qt.MatchContains):
                material = child.data(0x0100)
                hide = (material["name"].lower().find(text) == -1
                        and ("ui_name" not in material or get_ingame_string(material["ui_name"]).lower().find(text) == -1)
                        and ("tags" not in material or material["tags"].lower().find(text) == -1))
                child.setHidden(hide)
        materials_search.textChanged.connect(search_materials)

    def canvasChanged(self, canvas):
        pass

class XMLElement():
    def __init__(self, tag="", attrib={}):
        self.tag = tag
        self.attrib = attrib
        self.children = []

def parse_attribs(xml_text):
    matches = re.findall(r'(\S+)\s*=\s*"(\S*)"', xml_text)
    attrib = {}
    for key, value in matches:
        attrib[key] = value
    return attrib

#not super robust but good enough to get the data I need
def parse_element(xml_text):
    element = XMLElement()
    open_tag_start = xml_text.find("<")
    is_closing_tag = (xml_text[open_tag_start+1] == '/')
    if(is_closing_tag):
        open_tag_start += 1
    open_tag_end = xml_text.find(">")
    is_closing_tag |= (xml_text[open_tag_end-1] == '/')
    tag_name_end = open_tag_start+1+re.search(r"[\s>/]", xml_text[open_tag_start+1:]).start()
    element.tag = xml_text[open_tag_start+1:tag_name_end]
    element.attrib = parse_attribs(xml_text[tag_name_end+1:open_tag_end])
    found_closing_tag = is_closing_tag
    current_spot = open_tag_end+1
    child_tags = []
    while not found_closing_tag and current_spot < len(xml_text):
        tag_step, found_closing_tag, child_element = parse_element(xml_text[current_spot:])
        child_tag = child_element.tag
        child_tags.append(child_tag)
        current_spot += tag_step
        if(found_closing_tag):
            break
        element.children.append(child_element)
    close_tag_end = current_spot
    return close_tag_end, is_closing_tag, element

def parse_xml(filename):
    #preprocess files to handle noita's non-standard xml's
    filename = re.sub(r"\$\[(\d+)-(\d+)\]", lambda m: m.group(1), filename)
    try:
        with open(filename, "r") as file:
            xml_text = file.read()
            xml_text = re.sub(r"<!--.*?-->", '', xml_text, flags=re.DOTALL)
            _, _, element = parse_element(xml_text)
            return element
    except:
        return XMLElement()

#search for filename in mod dir and unpacked dir
def find_game_file(filename):
    filepaths = [
        os.path.join(noita_game_path, filename),
        os.path.join(noita_data_path, filename),
    ]

    doc = KI.activeDocument()
    if(doc):
        work_dir, map_name = os.path.split(doc.fileName())
        mod_files_dir = os.path.join(work_dir, "mod_files")
        filepaths = [filename.replace('mods/<mod_name>', mod_files_dir)]+filepaths
    #TODO: check workshop files, need to replace numbers with name in mod_id.txt

    for filepath in filepaths:
        if(os.path.isfile(filepath)):
            return filepath
    # raise FileNotFoundError("Could not find "+filename)
    return filename

class Sprite:
    def __init__(self, filename, offset_x = 0, offset_y = 0, centered = False, absolute_path = False):
        ext = os.path.splitext(filename)[1]
        rect = None
        self.filename = ""
        if(centered):
            offset_x = 0
            offset_y = 0
        if(ext == ".png"):
            self.filename = filename
        elif(ext == ".xml"):
            # sprite_xml = ET.parse(os.path.join(noita_data_path, filename))
            # root = sprite_xml.getroot()
            try:
                #TODO: if the file path begins with mods, search for locations it could be
                root = parse_xml(find_game_file(filename))
            except:
                root = XMLElement()
            if("filename" in root.attrib):
                self.filename = root.attrib["filename"]
            if("offset_x" in root.attrib):
                offset_x += float(root.attrib["offset_x"])
            if("offset_y" in root.attrib):
                offset_y += float(root.attrib["offset_y"])
            default_animation = None
            if("default_animation" in root.attrib):
                default_animation = root.attrib["default_animation"]

            for comp in root.children:
                if(comp.tag == "RectAnimation" and (default_animation is None or "name" in comp.attrib and default_animation == comp.attrib["name"])):
                    self.pos_x = 0
                    self.pos_y = 0
                    self.frame_width  = 32
                    self.frame_height = 32
                    if("pos_x" in comp.attrib):
                        self.pos_x = float(comp.attrib["pos_x"])
                    if("pos_y" in comp.attrib):
                        self.pos_y = float(comp.attrib["pos_y"])
                    if("frame_width" in comp.attrib):
                        self.frame_width  = float(comp.attrib["frame_width"])
                    if("frame_height" in comp.attrib):
                        self.frame_height = float(comp.attrib["frame_height"])
                    rect = QRect(self.pos_x,self.pos_y,self.frame_width,self.frame_height)
                    break

        if(not self.filename):
            self.filename = os.path.join(plugin_path, "unknown.png")
            centered = True
            absolute_path = True

        full_path = self.filename if absolute_path else find_game_file(self.filename)
        self.image = QImage(full_path)
        if(rect):
            self.image = self.image.copy(rect)
        self.image_array = QByteArray()
        image_buffer = QBuffer()
        image_buffer.setBuffer(self.image_array)
        self.image.save(image_buffer, "PNG")
        image_buffer.close()

        self.width  = self.image.width()
        self.height = self.image.height()
        if(centered):
            offset_x += self.width//2
            offset_y += self.height//2

        self.offset_x = offset_x
        self.offset_y = offset_y

class EntityField:
    def __init__(self, name, label, type, tooltip=""):
        self.name = name
        self.label = label
        self.type = type
        self.tooltip = tooltip
        self.widget = None
        self.label_widget = None
        data = {"text_line":"", "text_box":"", "boolean":0}[type]
        def get_data():
            nonlocal data
            return data
        self.get_data = get_data
        self.set_data = lambda info: None

    def add_widget(self, layout):
        if(not self.label_widget):
            self.label_widget = QLabel(self.label)
        self.label_widget.setToolTip(self.tooltip)
        if(not self.widget):
            if(self.type == "text_line"):
                self.widget = QLineEdit("")
                self.get_data = self.widget.text
                def set_data(info):
                    nonlocal self
                    self.widget.setText(info[self.name])
                self.set_data = set_data
            if(self.type == "text_box"):
                self.widget = QTextEdit("")
                self.widget.setSizePolicy(QSizePolicy.Policy.Minimum,
                                          QSizePolicy.Policy.Expanding)
                self.widget.setMinimumHeight(70)
                self.get_data = self.widget.toPlainText
                def set_data(info):
                    nonlocal self
                    self.widget.setPlainText(info[self.name])
                self.set_data = set_data
            if(self.type == "boolean"):
                self.widget = QCheckBox("")
                self.get_data = self.widget.checkState
                def set_data(info):
                    nonlocal self
                    self.widget.setCheckState(info[self.name])
                self.set_data = set_data
        if(self.type == "text_box"):
            layout.addRow(self.label_widget)
            layout.addRow(self.widget)
        else:
            layout.addRow(self.label_widget, self.widget)
        self.label_widget.setHidden(False)
        self.widget.setHidden(False)

class Entity:
    def __init__(self, filename, name="", tags="",
                 sprite=Sprite(os.path.join(plugin_path, "unknown.png"), 0, 0, centered=True, absolute_path=True),
                 extra_fields=[]):
        self.filename = filename
        self.name = name
        self.tags = tags
        self.sprite = sprite
        self.extra_fields = extra_fields

    def from_xml(filename, game_file_prefix=""):
        root = parse_xml(find_game_file(filename))

        name = ""
        tags = ""
        image_file = ""

        if("name" in root.attrib):
            name = get_ingame_string(root.attrib["name"])
        if("tags" in root.attrib):
            tags = root.attrib["tags"]

        offset_x = 0
        offset_y = 0
        centered = False
        best_sprite_priority = 0

        def search_xml_tree(node, sprite_priority=0):
            nonlocal tags
            nonlocal image_file
            nonlocal offset_x
            nonlocal offset_y
            nonlocal best_sprite_priority
            for comp in node.children:
                if(comp.tag == "Base"):
                    base_file = comp.attrib["file"]
                    base_root = parse_xml(find_game_file(base_file))
                    if("tags" in base_root.attrib):
                        tags += ","+base_root.attrib["tags"]
                    search_xml_tree(base_root, sprite_priority = sprite_priority+1)
                if(comp.tag == "SpriteComponent" or comp.tag == "PhysicsImageShapeComponent" and (not image_file or sprite_priority < best_sprite_priority)):
                    if("image_file" in comp.attrib):
                        image_file = comp.attrib["image_file"]
                        best_sprite_priority = sprite_priority
                        if("offset_x" in comp.attrib):
                            offset_x += float(comp.attrib["offset_x"])
                        if("offset_y" in comp.attrib):
                            offset_y += float(comp.attrib["offset_y"])
                        if("centered" in comp.attrib):
                            centered = True
                search_xml_tree(comp, sprite_priority)

        search_xml_tree(root)

        sprite = Sprite(image_file, offset_x, offset_y, centered)
        return Entity(game_file_prefix+filename, name, tags, sprite)

    def add_widgets(self, layout):
        for field in self.extra_fields:
            field.add_widget(layout)

    def extra_data(self):
        return {field.name:field.get_data() for field in self.extra_fields}

    def load_info(self, info):
        for field in self.extra_fields:
            field.set_data(info)

    def info(self):
        data = {"filename":self.filename,"x":self.sprite.offset_x,"y":self.sprite.offset_y}
        data.update(self.extra_data())
        return json.dumps(data)

    def get_svg(self):
        encoded_image = str(self.sprite.image_array.toBase64())[1:]
        return entity_svg_template.format(info=self.info(), data=encoded_image,
                                          width=self.sprite.width, height=self.sprite.height)

class EntitiesDocker(DockWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Noita Entities")

        splitter = QSplitter(self)
        splitter.setLayout(QVBoxLayout())
        splitter.setOrientation(Qt.Vertical)
        self.setWidget(splitter)

        extra_fields = QWidget(splitter)
        extra_fields.setLayout(QFormLayout())
        extra_fields.setMinimumHeight(100)
        # extra_fields.setSizePolicy(QSizePolicy.Policy.Minimum,
        #                            QSizePolicy.Policy.MinimumExpanding)
        # extra_fields.layout().setSizeConstraint(QLayout.SetMinimumSize)
        # extra_fields.layout().setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        extra_fields.layout().setLabelAlignment(Qt.AlignRight)
        splitter.addWidget(extra_fields)

        main_widget = QWidget(self)
        main_widget.setLayout(QVBoxLayout())
        splitter.addWidget(main_widget)
        splitter.setStretchFactor(1,1)

        selected_entity_line = QWidget(main_widget)
        selected_entity_line.setLayout(QHBoxLayout())
        main_widget.layout().addWidget(selected_entity_line)

        get_entity_button = QPushButton("Get Selected")
        selected_entity_line.layout().addWidget(get_entity_button)

        update_entity_button = QPushButton("Update Selected")
        selected_entity_line.layout().addWidget(update_entity_button)

        entities_label_line = QWidget(main_widget)
        entities_label_line.setLayout(QHBoxLayout())
        entities_label_line.layout().setContentsMargins(0,0,0,0)
        main_widget.layout().addWidget(entities_label_line)

        entities_text = QLabel("Search:", entities_label_line)
        entities_label_line.layout().addWidget(entities_text)

        entities_search = QLineEdit(entities_label_line)
        entities_label_line.layout().addWidget(entities_search)

        entities_box = QListWidget(main_widget)
        entities_box.setSizePolicy(QSizePolicy.Policy.Minimum,
                                   QSizePolicy.Policy.Minimum)
        entities_box.setViewMode(QListView.IconMode)
        entities_box.setUniformItemSizes(True)
        entities_box.setResizeMode(QListView.ResizeMode.Adjust)
        entities_box.setMinimumHeight(30)
        entities_box.setMovement(QListView.Static)

        entities_box.setDragDropMode(QAbstractItemView.DragDrop)

        def mime_types():
            return ["image/svg+xml"]

        entities_box.mimeTypes = mime_types

        def mime_data(items):
            nonlocal self
            entity = items[0].data(0x100)

            data = QMimeData()
            encoded_data = QByteArray.fromRawData(entity.get_svg().encode('utf-8'))
            data.setData("image/svg+xml", encoded_data)
            return data
        entities_box.mimeData = mime_data

        main_widget.layout().addWidget(entities_box, 2)

        self.entities = []

        self.entities.append(Entity("spawn_marker", "Spawn Location", "spawn,player,pos,position",
                                    sprite=Sprite(os.path.join(plugin_path, "spawn_marker.png"), 10, 13, absolute_path=True)))

        self.entities.append(Entity("other_entity", "Other Entity", "other,entity,filename",
                                    sprite=Sprite(os.path.join(plugin_path, "unknown.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("other_filename", "Filename", "text_line", "The filename of the entity you want to place.")]))

        self.entities.append(Entity("script", "Custom Lua Script", "custom,script,lua,code",
                                    sprite=Sprite(os.path.join(plugin_path, "custom_script.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("script", "Script (x, y)", "text_box", "This script will be executed when the region is loaded, x and y are the coordinates of the position this script is placed")]))

        self.entities.append(Entity("spawn_perk", "Spawn Perk", "spawn,perk,perks",
                                    sprite=Sprite(os.path.join(plugin_path, "spawn_perk.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("perk_id", "Perk ID", "text_line", "The id of the perk. A list of perk ids can be found on the noita wiki"),
                                                  EntityField("remove_other_perks", "Remove Other Perks", "boolean", "If enabled all other loaded perks will be removed on pickup (unless you have Perk Lottery)")]))

        self.entities.append(Entity("spawn_flask", "Spawn Flask", "spawn,potion,flask,material,bottle",
                                    sprite=Sprite(os.path.join(plugin_path, "spawn_flask.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("material_names", "Materials", "text_line", "A comma seperated list of material names, as defined in data/materials.xml"),
                                                  EntityField("material_amounts", "Amounts (1000=100%)", "text_line", "A comma seperated list of amounts")]))

        self.entities.append(Entity("spawn_card", "Spawn Spell Card", "spawn,spell,card,action",
                                    sprite=Sprite(os.path.join(plugin_path, "spawn_card.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("action_id", "Action ID", "text_line", "The id of the spell. A list of spell ids can be found on the noita wiki")]))

        self.entities.append(Entity("spawn_wand", "Spawn Wand", "spawn,wand,rod,stick",
                                    sprite=Sprite(os.path.join(plugin_path, "spawn_wand.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[EntityField("wand_file", "Filename", "text_line", "The filename of the wand to be spawned, spells that would normally spawn on that wand are deleted"),
                                                  EntityField("ac_actions", "Always Casts", "text_line", "A comma separated list of action ids. A list of spell action ids can be found on the noita wiki"),
                                                  EntityField("actions", "Spells", "text_line", "A comma separated list of action ids. A list of spell action ids can be found on the noita wiki")]))

        self.entities.append(Entity("portal", "Portal", "portal,teleport",
                                    sprite=Sprite(os.path.join(plugin_path, "portal.png"), 0, 0, centered=True, absolute_path=True),
                                    extra_fields=[
                                        EntityField("target_x", "Target x", "text_line", "Destination x coordinate"),
                                        EntityField("target_y", "Target y", "text_line", "Destination y coordinate"),
                                        EntityField("target_x_is_absolute_position", "Absolute x", "boolean", "If selected the target x coordinate is the absolute coordinate, otherwise it is relative to the portal location"),
                                        EntityField("target_y_is_absolute_position", "Absolute y", "boolean", "If selected the target y coordinate is the absolute coordinate, otherwise it is relative to the portal location"),
                                    ]))
        os.chdir(noita_data_path)
        for filename in Path("data/entities").rglob("*.xml"):
            self.entities.append(Entity.from_xml(str(filename)))

        self.custom_entities = []

        n_cols = 5

        def add_entity(entity):
            nonlocal entities_box
            entity_label = entity.name if entity.name else os.path.basename(entity.filename)
            entity_tooltip = entity.name+" ("+entity.filename+")" if entity.name else entity.filename
            icon_pixmap = QPixmap.fromImage(entity.sprite.image).scaled(QSize(32, 32), Qt.KeepAspectRatio)
            # icon_pixmap = QPixmap.fromImage(entity.sprite.image)
            entity_button = QListWidgetItem(QIcon(icon_pixmap), entity_label, entities_box)
            entity_button.setSizeHint(QSize(48, 48))
            entity_button.setTextAlignment(0x0024)
            entity_button.setToolTip(entity_tooltip)
            entity_button.setData(0x0100, QVariant(entity))

            entities_box.addItem(entity_button)
            return entity_button

        def remove_entity(entity_button):
            nonlocal entities_box
            entities_box.takeItem(entities_box.indexFromItem(entity_button).row())

        self.add_entity = add_entity
        self.remove_entity = remove_entity

        for i, entity in enumerate(self.entities):
            add_entity(entity)

        def search_entities(text):
            nonlocal entities_box
            text = text.lower()
            for child in entities_box.findItems("", Qt.MatchContains):
                entity = child.data(0x0100)
                hide = (entity.name.lower().find(text) == -1
                        and entity.tags.lower().find(text) == -1
                        and entity.filename.lower().find(text) == -1)
                child.setHidden(hide)
        entities_search.textChanged.connect(search_entities)

        def update_entity_selection():
            nonlocal entities_box
            nonlocal extra_fields
            while(True):
                item = extra_fields.layout().takeAt(0)
                if(not item):
                    break
                widget = item.widget()
                if(widget):
                    widget.setHidden(True)
            selected_items = entities_box.selectedItems()
            if(len(selected_items) > 0):
                entity = selected_items[0].data(0x0100)
                entity.add_widgets(extra_fields.layout())
            # extra_fields.adjustSize()
        entities_box.itemSelectionChanged.connect(update_entity_selection)

        def get_entity():
            nonlocal entities_box
            doc = KI.activeDocument()
            if(not doc):
                return
            data, shape, layer = find_selected_entity_info(doc.rootNode())
            if(not data):
                return
            for child in entities_box.findItems("", Qt.MatchContains):
                entity = child.data(0x0100)
                if(entity.filename == data["filename"]):
                    index = entities_box.indexFromItem(child)
                    entities_box.setCurrentIndex(index)
                    entity.load_info(data)
                    break

        def update_entity():
            nonlocal entities_box
            doc = KI.activeDocument()
            if(not doc):
                return
            data, shape, layer = find_selected_entity_info(doc.rootNode())
            if(not data):
                return
            selected_items = entities_box.selectedItems()
            if(len(selected_items) > 0):
                entity = selected_items[0].data(0x0100)
                transform = shape.transformation()
                shape.remove()
                shape = layer.addShapesFromSvg(entity.get_svg())[0]
                ppi = doc.resolution()
                shape.setTransformation(QTransform(72/ppi, 0, 0, 72/ppi, transform.dx(), transform.dy()))
                shape.select()
                shape.update()

        get_entity_button.clicked.connect(get_entity)
        update_entity_button.clicked.connect(update_entity)

    def canvasChanged(self, canvas):
        for entity in self.custom_entities:
            self.remove_entity(entity)
        self.custom_entities = []

        doc = KI.activeDocument()
        if(doc):
            unblur_entities(doc.resolution(), doc.rootNode(), QPoint(0,0))
            try:
                work_dir, map_name = os.path.split(doc.fileName())
                mod_files_dir = os.path.join(work_dir, "mod_files")

                os.chdir(mod_files_dir)
                non_entity_xmls = ["mod.xml", "workshop.xml", "compatibility.xml"]
                for filename in Path(".").rglob("*.xml"):
                    if(str(filename) in non_entity_xmls):
                        continue
                    entity = Entity.from_xml(os.path.join("mods/<mod_name>", str(filename)))
                    self.custom_entities.append(self.add_entity(entity))
            except:
                pass

        # def update_actual_entity_file():
        #     doc = KI.activeDocument()
        #     map_dir = os.path.splitext(doc.fileName())[0]
        #     # load_entity_data(doc)
        #     update_entity_data()
        #     save_entity_data(doc, actually_save=True)

        # for action in KI.actions():
        #     if(action.text() == "&Save"):
        #         action.triggered.connect(update_actual_entity_file)
        #         break

KI.addDockWidgetFactory(DockWidgetFactory("noita_editor", DockWidgetFactoryBase.DockRight, NoitaEditorDocker))
KI.addDockWidgetFactory(DockWidgetFactory("noita_materials", DockWidgetFactoryBase.DockRight, MaterialsDocker))
KI.addDockWidgetFactory(DockWidgetFactory("noita_entities", DockWidgetFactoryBase.DockRight, EntitiesDocker))
