import os, string
from os import path
from glob import glob
from nipype.interfaces.base import (TraitedSpec, 
                                    DynamicTraitedSpec, 
                                    InputMultiPath, 
                                    File,
                                    Directory, 
                                    traits, 
                                    BaseInterface,
                                   )
import dicom
import dcmstack
from dcmstack.dcmmeta import NiftiWrapper
import nibabel as nb

def sanitize_path_comp(path_comp):
    result = []
    for char in path_comp:
        if not char in string.letters + string.digits + '-_.':
            result.append('_')
        else:
            result.append(char)
    return ''.join(result)

class NiftiGeneratorBaseInputSpec(TraitedSpec):
    out_format = traits.Str(desc="String which can be formatted with "
                            "meta data to create the output filename(s)")
    out_ext = traits.Str('.nii.gz', 
                         usedefault=True, 
                         desc="Determines output file type")

class NiftiGeneratorBase(BaseInterface):
    def _get_out_path(self, meta):
        if self.inputs.out_format:
            out_fmt = self.inputs.out_format
        else:
            out_fmt = []
            if 'SeriesNumber' in meta:
                out_fmt.append('%(SeriesNumber)03d')
            if 'ProtocolName' in meta:
                out_fmt.append('%(ProtocolName)s')
            elif 'SeriesDescription' in meta:
                out_fmt.append('%(SeriesDescription)s')
            else:
                out_fmt.append('sequence')
            out_fmt = '-'.join(out_fmt)
        out_fn = (out_fmt % meta) + self.inputs.out_ext
        out_fn = sanitize_path_comp(out_fn)
        return path.join(os.getcwd(), out_fn)

class DcmStackInputSpec(NiftiGeneratorBaseInputSpec):
    dicom_files = traits.Either(InputMultiPath(File(exists=True)),
                                Directory(exists=True),
                                traits.Str(), 
                                mandatory=True)
    embed_meta = traits.Bool(desc="Embed DICOM meta data into result")
    exclude_regexes = traits.List(desc="Meta data to exclude, suplementing any default exclude filters")
    include_regexes = traits.List(desc="Meta data to include, overriding any exclude filters")
    
class DcmStackOutputSpec(TraitedSpec):
    out_file = traits.File(exists=True)

class DcmStack(NiftiGeneratorBase):
    '''Create one Nifti file from a set of DICOM files'''
    input_spec = DcmStackInputSpec
    output_spec = DcmStackOutputSpec
    
    def _get_filelist(self, trait_input):
        if isinstance(trait_input, str):
            if path.isdir(trait_input):
                return glob(path.join(trait_input, '*.dcm'))
            else:
                return glob(trait_input)
        
        return trait_input
    
    def _run_interface(self, runtime):
        src_paths = self._get_filelist(self.inputs.dicom_files)
        include_regexes = dcmstack.default_key_incl_res
        if not self.inputs.include_regexes is Undefined:
            include_regexes += self.inputs.include_regexes
        exclude_regexes = dcmstack.default_key_excl_res
        if not self.inputs.exclude_regexes is Undefined:
            exclude_regexes += self.inputs.exclude_regexes
        meta_filter = dcmstack.make_key_regex_filter(exclude_regexes, 
                                                     include_regexes)   
        stack = dcmstack.DicomStack(meta_filter=meta_filter)
        for src_path in src_paths:
            src_dcm = dicom.read_file(src_path, force=True)
            stack.add_dcm(src_dcm)
        nii = stack.to_nifti(embed_meta=True)
        nw = NiftiWrapper(nii)
        self.out_path = self._get_out_path(nw.meta_ext.get_class_dict(('global', 'const')))
        if not self.inputs.embed_meta:
            nw.remove_extension()
        nb.save(nii, self.out_path)
        return runtime
        
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["out_file"] = self.out_path
        return outputs

class GroupAndStackOutputSpec(TraitedSpec):
    out_list = traits.List(desc="List of output nifti files")

class GroupAndStack(NiftiGeneratorBase):
    '''Create (potentially) multiple Nifti files for a set of DICOM 
    files.'''
    input_spec = DcmStackInputSpec
    output_spec = GroupAndStackOutputSpec
    
    def _run_interface(self, runtime):
        src_paths = self._get_filelist(self.inputs.dicom_files)
        stacks = \
            dcmstack.parse_and_stack(src_paths, 
                                     key_format=self.inputs.out_format
                                    )
        
        self.out_list = []
        for key, stack in stacks.iteritems():
            nw = NiftiWrapper(stack.to_nifti(embed_meta=self.inputs.embed_meta))
            out_path = self._get_out_path(nw.meta_ext.get_class_dict(('global', 'const')))
            nb.save(nw.nii_img, out_path)
            self.out_list.append(out_path)
            
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["out_list"] = self.out_list
        return outputs

class LookupMetaInputSpec(TraitedSpec):
    in_file = File(mandatory=True, 
                   exists=True, 
                   desc='The input Nifti file')
    meta_keys = traits.List(mandatory=True,
                            desc='List of meta data keys to lookup')

class LookupMeta(BaseInterface):
    '''Lookup meta data values from a Nifti with embeded meta data.'''
    input_spec = LookupMetaInputSpec
    output_spec = DynamicTraitedSpec

    def _outputs(self):
        outputs = LookupMeta(Fastfit, self)._outputs()
        undefined_traits = {}
        for meta_key in self.inputs.meta_keys:
            outputs.add_trait(meta_key, traits.Any)
            undefined_traits[meta_key] = Undefined
        outputs.trait_set(trait_change_notify=False, **undefined_traits)
        #Not sure why this is needed
        for meta_key in meta_keys:
            _ = getattr(outputs, meta_key)
        return outputs
        
    def _run_interface(self, runtime):
        nw = NiftiWrapper.from_filename(self.inputs.in_file)
        self.result = {}
        for meta_key in self.inputs.meta_keys:
            self.result[meta_key] = nw.meta_ext.get_values(meta_key)
            
        return runtime
            
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs.update(self.result)
        return outputs
       
class CopyMetaInputSpec(TraitedSpec):
    src_file = traits.File(mandatory=True,
                         exists=True,
                        )
    dest_file = traits.File(mandatory=True,
                            exists=True)
    include_classes = traits.List(desc="List of specific meta data "
                                  "classifications to include. If not "
                                  "specified include everything.")
    exclude_classes = traits.List(desc="List of meta data "
                                  "classifications to exclude")
    
class CopyMetaOutputSpec(TraitedSpec):
    dest_file = traits.File(exists=True)
    
class CopyMeta(BaseInterface):
    input_spec = CopyMetaInputSpec
    output_spec = CopyMetaOutputSpec
    
    '''Copy meta data from one Nifti file to another.'''
    def _run_interface(self, runtime):
        src = NiftiWrapper.from_filename(self.inputs.src_file)
        dest_nii = nb.load(self.inputs.dest_file)
        dest = NiftiWrapper(dest_nii, make_empty=True)
        classes = src.meta_ext.get_valid_classes()
        if self.inputs.include_classes:
            classes = [cls 
                       for cls in classes 
                       if cls in self.inputs.include_classes
                      ]
        if self.inputs.exclude_classes:
            classes = [cls 
                       for cls in classes 
                       if not cls in self.inputs.exclude_classes
                      ]
        
        for cls in classes:
            src_dict = src.meta_ext.get_class_dict(cls)
            dest_dict = dest.meta_ext.get_class_dict(cls)
            dest_dict.update(src_dict)
            
        self.out_path = path.join(os.getcwd(), 
                                  path.basename(self.inputs.dest_file))
        dest.to_filename(self.out_path)
        
        return runtime
        
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['dest_file'] = self.out_path
        return outputs

class MergeNiftiInputSpec(NiftiGeneratorBaseInputSpec):
    in_files = traits.List(mandatory=True,
                           desc="List of Nifti files to merge")
    sort_order = traits.Either(traits.Str(),
                               traits.List(),
                               desc="One or more meta data keys to "
                               "sort files by.")
    merge_dim = traits.Int(desc="Dimension to merge along. If not "
                           "specified, the last singular or "
                           "non-existant dimension is used.")
        
class MergeNiftiOutputSpec(TraitedSpec):
    out_file = traits.File(exists=True,
                           desc="Merged Nifti file")
        
def make_key_func(meta_keys, index=None):
    def key_func(src_nii):
        result = [src_nii.get_meta(key, index) for key in meta_keys]
        return result
    
    return key_func
    
class MergeNifti(NiftiGeneratorBase):
    '''Merge multiple Nifti files into one. Merges together meta data 
    extensions as well.'''
    input_spec = MergeNiftiInputSpec
    output_spec = MergeNiftiOutputSpec
        
    def _run_interface(self, runtime):
        niis = [nb.load(fn) 
                for fn in self.inputs.in_files
               ]
        nws = [NiftiWrapper(nii, make_empty=True) 
               for nii in niis
              ]
        if self.inputs.sort_order:
            sort_order = self.inputs.sort_order
            if isinstance(sort_order, str):
                sort_order = [sort_order]
            nws.sort(key=make_key_func(sort_order))
        if self.inputs.merge_dim == traits.Undefined:
            merge_dim = None
        else:
            merge_dim = self.inputs.merge_dim
        merged = NiftiWrapper.from_sequence(nws, merge_dim)
        self.out_path = self._get_out_path(merged.meta_ext.get_class_dict(('global', 'const')))
        nb.save(merged.nii_img, self.out_path)
        return runtime
        
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['out_file'] = self.out_path
        return outputs

class SplitNiftiInputSpec(NiftiGeneratorBaseInputSpec):
    in_file = traits.File(exists=True,
                          mandatory=True,
                          desc="Nifti file to split")
    split_dim = traits.Int(desc="Dimension to split along. If not "
                           "specified, the last dimension is used.")
        
class SplitNiftiOutputSpec(TraitedSpec):
    out_list = traits.List(exists=True,
                           desc="Split Nifti files")
                           
class SplitNifti(NiftiGeneratorBase):
    '''Merge multiple Nifti files into one. Merges together meta data 
    extensions as well.'''
    input_spec = SplitNiftiInputSpec
    output_spec = SplitNiftiOutputSpec
        
    def _run_interface(self, runtime):
        self.out_list = []
        nii = nb.load(self.inputs.in_file)
        nw = NiftiWrapper(nii, make_empty=True)
        split_dim = None
        if self.inputs.split_dim == traits.Undefined:
            split_dim = None
        else:
            split_dim = self.inputs.split_dim
        for split_nw in nw.split(split_dim):
            out_path = self._get_out_path(split_nw.meta_ext.get_class_dict(('global', 'const')))
            nb.save(split_nw.nii_img, out_path)
            self.out_list.append(out_path)
            
        return runtime
        
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['out_list'] = self.out_list
        return outputs

