bl_info = {
    "name": "G-Code Generator",        # Название в списке аддонов
    "author": "Sergey Badin",             # Твое имя
    "version": (1, 0),                 # Версия аддона
    "blender": (3, 0, 0),              # Минимальная версия Blender (лучше ставить 3.0+)
    "location": "View3D > Sidebar > Tool Tab", # Где найти аддон
    "description": "Генерация G-кода из кривых в коллекции",
    "category": "Import-Export",       # Категория (для G-кода лучше Import-Export)
}

import bpy
from bpy import context
import os


# --- ТВОЯ ФУНКЦИЯ (вставь сюда свой код) ---
def makeGcode(collection_name, laserPower, speedMove, fileName, laserMode):
    print(f"Экспорт G-Code из коллекции: {collection_name}")
    print(f"Параметры: Power={laserPower}, Speed={speedMove}")
    print(f"Файл: {fileName}")
    print(f"LaserMode: {laserMode}")
    
#    gcode_collection = bpy.data.collections["gCode"]
    gcode_collection = bpy.data.collections[collection_name]
    if gcode_collection:
        with open(fileName,"w") as file:
            file.write("G90 (use absolute coordinates)\n")
            file.write(f"{laserMode} S0\n")
            file.write(f"F{speedMove}\n") # для сложных объектов 370 для обычных 380  gravirovka 5800 
            laserPower = f"S{laserPower}"
            sorted_objects = sorted(gcode_collection.objects, key=lambda obj: obj.name)
            for obj in sorted_objects:
                if obj.type == 'CURVE':
                    print(obj.name)
                    matrix = obj.matrix_world
                    for spline in obj.data.splines:
                        if spline.type == 'BEZIER':
                            points = spline.bezier_points
                            x0="x"
                            y0="y"
                            i = 0
                            for point in points:
                                world_coords = matrix @ point.co
                                mmCoords = world_coords*1000
                                x=f"{mmCoords.x:.3f}"
                                y=f"{mmCoords.y:.3f}"
                                if x != x0 or y != y0:
                                    i = i + 1
                                    if i ==1:
                                        file.write(f"G0X{x}Y{y}\n")
                                    else:    
                                        if i == 2:
                                            file.write(f"G1X{x}Y{y}{laserPower}\n")
                                        else:
                                            file.write(f"X{x}Y{y}\n")    
                                x0 = x
                                y0 = y        
                            if spline.use_cyclic_u:
                                world_coords = matrix @ points[0].co
                                mmCoords = world_coords*1000
                                file.write(f"X{mmCoords.x:.3f}Y{mmCoords.y:.3f}\n")
                            else:
                                print("Без цикла")    
                            file.write("S0\n")
                        else:
                            print("Кривая не бизье!")            
                else:
                    print("Активный объект не является кривой.")
            file.write("M5 S0\n")                    
            file.write("G0 X0 Y0 Z0 (move back to origin)\n")                    
            file.write("%")
    else:
        print("Нет коллекции gCode")

    
    # Твоя логика здесь...
    # Например, доступ к объектам:
    # collection = bpy.data.collections.get(collection_name)
    # if collection:
    #     for obj in collection.objects:
    #         pass 
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
        makeGcode(
            collection_name=props.target_collection.name,
            laserPower=props.laser_power,
            speedMove=props.speed_move,
            fileName=bpy.path.abspath(props.file_path), # Превращает // в полный путь
            laserMode=props.laser_mode
        )
        
        self.report({'INFO'}, "G-Code успешно сгенерирован!")
        return {'FINISHED'}

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
    