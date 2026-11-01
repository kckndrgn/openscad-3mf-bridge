import sys, unittest, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge import CORE, get_source_meshes, convert
class ComponentTests(unittest.TestCase):
    def setUp(self):
        with zipfile.ZipFile(ROOT/'tests/fixtures/four_colors_components.3mf') as z:
            self.root=ET.fromstring(z.read('3D/3dmodel.model'))
    def test_nested_assembly_and_colors(self):
        verts,faces=get_source_meshes(self.root)
        self.assertEqual((len(verts),len(faces)),(32,48))
        bounds=[]
        for j in range(4):
            group=verts[j*8:(j+1)*8]
            bounds.append(tuple((min(float(v.get(k)) for v in group),max(float(v.get(k)) for v in group)) for k in ('x','y','z')))
        self.assertEqual(bounds,[((0,20),(10,30),(0,20)),((35,55),(10,30),(0,20)),((65,85),(10,30),(0,20)),((100,130),(10,20),(0,40))])
        with TemporaryDirectory() as d:
            output=Path(d)/'converted.3mf'
            convert(ROOT/'tests/fixtures/four_colors_components.3mf',output)
            with zipfile.ZipFile(output) as z:
                model=ET.fromstring(z.read('3D/Objects/object_1.model'))
                triangles=model.findall(f'.//{CORE}triangle')
                self.assertEqual({c:sum(t.get('paint_color')==c for t in triangles) for c in ('4','8','0C','1C')},{'4':12,'8':12,'0C':12,'1C':12})
    def test_cycle_rejected(self):
        assembly=self.root.find(f'./{CORE}resources/{CORE}object[@id="100"]/{CORE}components/{CORE}component')
        assembly.set('objectid','101')
        with self.assertRaisesRegex(ValueError,'Circular component reference'):
            get_source_meshes(self.root)
    def test_repeated_instances(self):
        build=self.root.find(f'{CORE}build')
        ET.SubElement(build,f'{CORE}item',{'objectid':'101','transform':'1 0 0 0 1 0 0 0 1 150 0 0'})
        verts,faces=get_source_meshes(self.root)
        self.assertEqual((len(verts),len(faces)),(64,96))
if __name__=='__main__':unittest.main()
