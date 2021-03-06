# -*- coding: utf-8 -*- 
__doc__ = 'create worksets'
from System.Collections.Generic import List
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import RoomTag
from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons
from scriptutils import logger
import functools
from scriptutils import this_script
from pprint import pprint
import re
import os
from pprint import pprint

app = __revit__.Application.Documents
uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document
selection = uidoc.Selection.GetElementIds()

cl = FilteredElementCollector(doc).WhereElementIsElementType()
selection = cl.OfCategory(BuiltInCategory.OST_RvtLinks).ToElementIds()


def file2ws_name(filename):
    symbols = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
               u"abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA")

    tr = {ord(a): ord(b) for a, b in zip(*symbols)}

    filename, ext = os.path.splitext(filename)
    ext = ext.replace('.', '')
    filename = re.sub(r'[^a-zA-Zа-яА-Я0-9_-]', '_', filename)
    filename = filename.translate(tr)

    return "00_{ext}_{filename}".format(ext=ext, filename=filename).upper()


class Check(object):
    def __init__(self, elements):

        self.elements = elements
        self.errors = {}
        self.fix_text = "Исправить ошибки?"

    def run(self):
        self.check_all()
        if len(self.errors.keys()) > 0:
            error_text = self.fix_text + "\n\n" + "\n\n".join(list(self.errors.keys()))

            q = TaskDialog.Show(type(self).__name__, error_text,
                                TaskDialogCommonButtons.Ok | TaskDialogCommonButtons.Cancel)
            if str(q) == "Ok":
                self.fix()

    def check_all(self):
        for k in self.elements.keys():
            els = self.elements[k]
            for e in els:
                self.check_one(e, k)

    def check_one(self, e):
        pass

    def fix(self):
        pass


class CheckPinned(Check):
    def __init__(self, elements):
        super(self.__class__, self).__init__(elements)

    def check_one(self, e, k):
        t = doc.GetElement(k)
        filename = t.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME).AsString()

        if e.Pinned == False:
            message = '%s instance not pinned' % (filename,)
            if message not in self.errors:
                self.errors[message] = []
            self.errors[message].append(e)

    def fix(self):
        t = Transaction(doc, 'Fix links - Pin')
        t.Start()
        for vv in self.errors.values():
            for e in vv:
                e.Pinned = True
        t.Commit()


class SaveSharedCoordinatesCallback(ISaveSharedCoordinatesCallback):
    def GetSaveModifiedLinksOption(self, link):
        return SaveModifiedLinksOptions.DisableSharedPositioning

    def __init__(self):
        pass


class CheckShared(Check):
    def __init__(self, elements):
        super(self.__class__, self).__init__(elements)

    def check_one(self, e, k):
        t = doc.GetElement(k)
        filename = t.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME).AsString()

        message = '%s has shared position enabled' % (filename,)
        if message not in self.errors:
            self.errors[message] = []
        self.errors[message].append(e)

    def fix(self):
        t = Transaction(doc, 'Fix links - Shared coordinates')
        t.Start()
        for vv in self.errors.values():
            for e in vv:
                type_id = e.GetTypeId()
                type_el = doc.GetElement(type_id)
                translation = XYZ(1, 0, 0)
                print(e.GetTotalTransform().BasisX, e.GetTotalTransform().BasisY, e.GetTotalTransform().BasisZ,
                      e.GetTotalTransform().Determinant, e.GetTotalTransform().Origin)
                try:
                    ElementTransformUtils.MoveElement(doc, e.Id, translation)
                except:
                    print("Move failed")
                print(type_el)
                print(type_el.SavePositions(SaveSharedCoordinatesCallback()))
        t.RollBack()


class CheckWorkset(Check):
    def __init__(self, elements):
        super(self.__class__, self).__init__(elements)
        self.allowed_pattern = r"(A[-_]{1}LNK|\.|00[-_]{1}|01[-_]{1}|#)"
        _all_worksets = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset).ToWorksets()
        self.all_worksets = {}

        for w in _all_worksets:
            self.all_worksets[w.Id.IntegerValue] = w.Name

    def check_one(self, e, k):
        # print(e.Id,k)
        ws_name = self.all_worksets[e.WorksetId.IntegerValue]
        m = re.match(self.allowed_pattern, ws_name, re.I)

        if not m:
            t = doc.GetElement(k)
            filename = t.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME).AsString()
            ws_name_new = file2ws_name(filename)
            message = '%s in %s --> %s' % (filename, ws_name, ws_name_new,)
            if message not in self.errors:
                self.errors[message] = []
            self.errors[message].append((e, ws_name_new))

    #
    def fix(self):
        needed_workset = set()
        [[needed_workset.add(v[1]) for v in vv] for vv in self.errors.values()]
        t = Transaction(doc, 'Workset')
        t.Start()

        for ws in needed_workset:
            if ws not in self.all_worksets.values():
                print("new worset %s" % ws)
                ws_new = Workset.Create(doc, ws)
                self.all_worksets[ws_new.Id.IntegerValue] = ws
                # e, new_value = self.errors[k]
        all_worksets_inv = {v: k for k, v in self.all_worksets.iteritems()}
        for vv in self.errors.values():
            for e, ws_name_new in vv:
                wsparam = e.get_Parameter(BuiltInParameter.ELEM_PARTITION_PARAM)
                if (wsparam == None):
                    continue
                wsparam.Set(all_worksets_inv[ws_name_new])
        t.Commit()


def collect_links():
    """
    Collects links from model in format
    { LinkType: [LinkInstance, LinkInstance, ... ] }

    :return:
    dict
    """

    links = {}

    cl = FilteredElementCollector(doc).OfCategory(
        BuiltInCategory.OST_RvtLinks).WhereElementIsNotElementType().ToElementIds()
    for e_id in cl:
        e = doc.GetElement(e_id)
        type_id = e.GetTypeId()
        if type_id not in links:
            links[type_id] = []
        links[type_id].append(e)

    return links


links = collect_links()
# pprint(links)
# CheckWorkset(links).run()
# CheckPinned(links).run()
CheckShared(links).run()
# pprint(ch_ws.errors)



# print links
