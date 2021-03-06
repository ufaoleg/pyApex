# -*- coding: utf-8 -*-
__doc__ = 'Move all elements based on specified level onto another level'
import csv
import os
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import *
from Autodesk.Revit.UI import TaskDialog
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from System.Collections.Generic import List
from scriptutils.userinput import SelectFromList, SelectFromCheckBoxes
from scriptutils import this_script
from revitutils import doc, selection, uidoc


class CheckBoxLevel:
    def __init__(self, level, default_state=False):
        self.level = level
        self.name = level.Name
        self.state = default_state

    def __str__(self):
        return self.name

    def __nonzero__(self):
        return self.state

    def __bool__(self):
        return self.state


def LevelChangePreselected(selected_ids, target_level_id):
    errors = []
    changed = []
    t = Transaction(doc, 'Change level to 0')
    t.Start()
    for e_id in selected_ids:
        el = doc.GetElement(e_id)
        try:
            levelID = el.LevelId  # Initial level of object, assigned on element creation
            LevelToElement = doc.GetElement(levelID)

            LevElev = LevelToElement.get_Parameter(BuiltInParameter.LEVEL_ELEV).AsValueString().replace(" ", "")

            offset = el.get_Parameter(BuiltInParameter.INSTANCE_FREE_HOST_OFFSET_PARAM)

            if not offset:
                offset = el.get_Parameter(BuiltInParameter.FAMILY_BASE_LEVEL_OFFSET_PARAM)

            if not offset:
                offset = el.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)

            finalElev = float(LevElev) + float(offset.AsValueString().replace(" ", ""))
            offset.SetValueString(str(finalElev))

            baselevel = el.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
            if not baselevel:
                baselevel = el.get_Parameter(BuiltInParameter.WALL_BASE_CONSTRAINT)

            baselevel.Set(target_level_id)
            changed.append(str(e_id.IntegerValue))
        except Exception as e:
            try:
                print("%s %s - %s" % (str(e_id.IntegerValue),str(el.GetType()),str(e)))
            except:
                print("%s - %s" % (str(e_id.IntegerValue), str(e)))
            errors.append(str(e_id.IntegerValue))
    t.Commit()

    return errors, changed

def main():
    cl_sheets = FilteredElementCollector(doc)
    levels_all = cl_sheets.OfCategory(BuiltInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()

    options = []
    for l in levels_all:
        cb = CheckBoxLevel(l)
        options.append(cb)

    if len(options) == 0:
        print("Levels wasn't found")
        return
    selected1 = SelectFromCheckBoxes.show(options, title='Select levels to delete', width=300,
                                               button_name='OK')

    if not selected1:
        print("Nothing selected")
        return

    selected_levels1 = [c.level for c in selected1 if c.state == True]
    options = [c for c in selected1 if c.state != True]
    # print(selected_levels1)
    selected2 = SelectFromList.show(options, title='Select target level', width=300,
                                          button_name='OK')

    if len(options) == 0:
        print("You selected all levels")
        return

    if not selected2:
        print("Nothing selected")
        return
    print(selected2)
    selected_levels2 = [c.level for c in selected2]
    target_level = selected_levels2[0]
    errors = set()
    changed = set()
    for l in selected_levels1:
        objects_to_change = []

        t = Transaction(doc, "Check level " + l.Name)
        t.Start()
        elements = doc.Delete(l.Id)
        t.RollBack()

        errors_, changed_ = LevelChangePreselected(elements, target_level.Id)

        errors = errors.union(set(errors_))
        changed = changed.union(set(changed_))

    if errors:
        print("Errors")
        print( ",".join(list(errors)))

    if changed:
        print("\nChanged")
        print( ",".join(list(changed)))

main()