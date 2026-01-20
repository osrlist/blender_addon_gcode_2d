bl_info = {
    "name": "G-Code Generator",        # Название в списке аддонов
    "author": "Sergey Badin",             # Твое имя
    "version": (1, 1),                 # Версия аддона
    "blender": (3, 0, 0),              # Минимальная версия Blender (лучше ставить 3.0+)
    "location": "View3D > Sidebar > Tool Tab", # Где найти аддон
    "description": "Генерация G-кода из кривых в коллекции",
    "category": "Import-Export",       # Категория (для G-кода лучше Import-Export)
}

import bpy
from bpy import context
import os

def get_xy_first_point(spline, obj):
    if not hasattr(spline, 'bezier_points') or not spline.bezier_points:
        return (float('inf'), float('inf'), [])  # Если это не Bezier или нет точек

    spline_list = []
    matrix = obj.matrix_world
    for point in spline.bezier_points:
        world_coords = matrix @ point.co
        mmCoords = world_coords * 1000
        spline_list.append((round(mmCoords.x, 3), round(mmCoords.y, 3)))

    if spline.use_cyclic_u:
        spline_list.append((spline_list[0][0], spline_list[0][1]))

    return (spline_list[0][0], spline_list[0][1], spline_list)

def addSpleineToList(sorted_splines, i, group):
    for (s, x_val) in sorted(group, key=lambda item: item[1], reverse=(i % 2 != 0)):
        if i % 2 == 0:
            if s[0][0] > s[1][0]:
                s.reverse() 
        else:
            if s[0][0] < s[1][0]:
                s.reverse() 
        sorted_splines.append(s)

def sort_bezier_splines_alternating(curve_objects):
    """
    Сортирует Bezier сплайны: по Y, затем четные по убыванию X, нечетные по возрастанию X.
    Учитывает только первые три знака после запятой.

    Args:
        curve_objects: Список объектов кривых.

    Returns:
        Отсортированный список Bezier сплайнов.
    """
    sorted_splines = []
    for obj in curve_objects:
        splines_with_coords = []
        for spline in obj.data.splines:
            if hasattr(spline, 'bezier_points'): # только Bezier
                x, y, list_coordinate = get_xy_first_point(spline, obj)
                splines_with_coords.append((list_coordinate, x, y))

        # Сортируем по Y сначала
        splines_with_coords.sort(key=lambda item: item[2])  # Сортируем по Y

        # Теперь сортируем внутри групп с одинаковой Y координатой, чередуя порядок X
        current_y = splines_with_coords[0][2]
        group = []
        i = 0
        for spline, x, y in splines_with_coords:
            if y == current_y:
                group.append((spline, x))
            else:
                # Обрабатываем группу с одинаковой Y
                addSpleineToList(sorted_splines, i, group)
                i += 1

                # Начинаем новую группу
                current_y = y
                group = [(spline, x)]

        # Обрабатываем последнюю группу
        addSpleineToList(sorted_splines, i, group)
        
        
    return sorted_splines

def print_sorted_bezier_splines_alternating(collection_name, laserPower, speedMove, fileName, laserMode):
    """
    Выводит в консоль отсортированные Bezier сплайны.
    """
    try:
        gcode_collection = bpy.data.collections[collection_name]
    except KeyError:
        print(f"Коллекция '{collection_name}' не найдена.")
        return False

    curve_objects = [obj for obj in gcode_collection.objects if obj.type == 'CURVE']

    if not curve_objects:
        print(f"В коллекции '{collection_name}' нет кривых.")
        return False
    
    sorted_objects = sorted(curve_objects, key=lambda obj: obj.name)

    bezier_curves = []
    for obj in sorted_objects:
        for spline in obj.data.splines:
            if hasattr(spline, 'bezier_points'):
                bezier_curves.append(obj)  # Добавляем объекты Bezier кривых, а не все

    if not bezier_curves:
        print(f"В коллекции '{collection_name}' нет Bezier кривых.")
        return False

    sorted_splines = sort_bezier_splines_alternating(sorted_objects)
    return makeGcode(sorted_splines, laserPower, speedMove, fileName, laserMode)

# --- ТВОЯ ФУНКЦИЯ (вставь сюда свой код) ---
def makeGcode(sorted_splines, laserPower, speedMove, fileName, laserMode):
    print(f"Параметры: Power={laserPower}, Speed={speedMove}")
    print(f"Файл: {fileName}")
    print(f"LaserMode: {laserMode}")

    with open(fileName, "w") as file:
        file.write("G90 (use absolute coordinates)\n")
        file.write(f"{laserMode} S0\n")
        file.write(f"F{speedMove}\n")  # для сложных объектов 370 для обычных 380  gravirovka 5800 
        laserPower = f"S{laserPower}"
        for spline in sorted_splines:
            x0 = "x"
            y0 = "y"
            i = 0
            for point in spline:
                x = f"{point[0]:.3f}"
                y = f"{point[1]:.3f}"
                if x != x0 or y != y0:
                    i = i + 1
                    if i == 1:
                        file.write(f"G0X{x}Y{y}S0\n")
                    else:
                        if i == 2:
                            file.write(f"G1X{x}Y{y}{laserPower}\n")
                        else:
                            file.write(f"X{x}Y{y}\n")
                x0 = x
                y0 = y

        file.write("M5 S0\n")
        file.write("G0 X0 Y0 Z0 (move back to origin)\n")
        file.write("%")
    return True
# ------------------------------------------

# 1. Хранилище настроек (свойства)
class GCodeProperties(bpy.types.PropertyGroup):
    # Выбор коллекции через пипетку/список
    target_collection: bpy.props.PointerProperty(
        name="Collection",
        type=bpy.types.Collection,
        description="Коллекция, из которой берутся кривые"
    )
    
    laser_power: bpy.props.IntProperty(
        name="Laser Power",
        default=380,
        max=1000,
        min=0,
        description="Мощность лазера"
    )
    
    speed_move: bpy.props.IntProperty(
        name="Speed Move",
        default=3200,
        min=0,
        description="Скорость передвижения"
    )
    
    file_path: bpy.props.StringProperty(
        name="File Path",
        subtype='FILE_PATH',
        description="Куда сохранить G-код",
        default="program.nc"
    )
    
    laser_mode: bpy.props.EnumProperty(
        name="Laser Mode",
        description="Выберите режим работы лазера",
        items=[
            ('M3', "M3 - Constant Power", "Постоянная мощность лазера"),
            ('M4', "M4 - Dynamic Power", "Динамическое управление мощностью")
        ],
        default='M4'
    )    

# 2. Оператор (Кнопка "Extract")
class OBJECT_OT_GCodeExtract(bpy.types.Operator):
    bl_idname = "object.extract_gcode"
    bl_label = "Extract G-Code"
    bl_description = "Запустить генерацию G-кода"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Получаем доступ к свойствам
        props = context.scene.gcode_tool
        
        # Проверка на наличие коллекции
        if not props.target_collection:
            self.report({'ERROR'}, "Выберите коллекцию!")
            return {'CANCELLED'}

        # Вызов твоей функции с передачей параметров
        result = print_sorted_bezier_splines_alternating(
            collection_name=props.target_collection.name,
            laserPower=props.laser_power,
            speedMove=props.speed_move,
            fileName=bpy.path.abspath(props.file_path), # Превращает // в полный путь
            laserMode=props.laser_mode
        )
        
        if result:
            self.report({'INFO'}, "G-Code успешно сгенерирован!")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Смотри пояснения в консоли!")
            return {'CANCELLED'}


class VIEW3D_PT_GCodePanel(bpy.types.Panel):
    bl_label = "GCode Generator"
    bl_idname = "VIEW3D_PT_gcode_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.gcode_tool
        
        # 1. Включаем стандартное разделение (Label слева, Поле справа)
        # Это сделает вид как в стандартных настройках Blender
        layout.use_property_split = True
        layout.use_property_decorate = False  # Убираем лишние иконки анимации справа

        # 2. Создаем "Box" (рамку), которая визуально сгруппирует элементы
        main_box = layout.box()
        
        # Создаем колонку внутри бокса
        col = main_box.column(align=True)
        
        # Добавляем параметры
        col.prop(props, "target_collection")
        col.prop(props, "laser_mode")
        col.prop(props, "laser_power")
        col.prop(props, "speed_move")
        col.prop(props, "file_path")
        
        # Небольшой отступ перед кнопкой
        main_box.separator()
        
        # 3. Кнопка "Extract" внутри этой же рамки
        # Если хотим, чтобы кнопка была на всю ширину без разделения на Label, 
        # сбрасываем use_property_split только для этой строки
        row = main_box.row()
        row.scale_y = 1.5 # Делаем кнопку чуть выше
        row.operator("object.extract_gcode", icon='EXPORT')


classes = (
    GCodeProperties,
    OBJECT_OT_GCodeExtract,
    VIEW3D_PT_GCodePanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Создаем ссылку на свойства в объекте сцены
    bpy.types.Scene.gcode_tool = bpy.props.PointerProperty(type=GCodeProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.gcode_tool

if __name__ == "__main__":
    register()
    