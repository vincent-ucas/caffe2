from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from caffe2.python import core, schema
from caffe2.python.layers.layers import (
    ModelLayer,
)
import numpy as np


class SparseToDense(ModelLayer):
    _known_types = ['FLOAT', 'ID_LIST']

    def __init__(self, model, input_record, input_specs,
                 name='sparse_to_dense', **kwargs):
        """
        `input_specs` follows the format of FeatureSpec from schema. To be more
        precise it's a namedtuple that should have:
            'feature_type', 'feature_names', 'feature_ids'
        """
        super(SparseToDense, self).__init__(model, name,
                                            input_record, **kwargs)

        self.input_specs = input_specs

        outputs = []
        for field, feature_specs in self.input_specs:
            assert len(feature_specs.feature_names) ==\
                len(feature_specs.feature_ids)
            if feature_specs.feature_type == 'FLOAT':
                outputs.append((
                    field,
                    schema.Scalar(
                        (np.float32, len(feature_specs.feature_ids)),
                        model.net.NextScopedBlob(name + '_' + field + '_output')
                    )
                ))
            elif feature_specs.feature_type == 'ID_LIST':
                outputs.append((
                    field,
                    schema.Struct(
                        ('ranges',
                            schema.Scalar(
                                (
                                    np.int32,
                                    (len(feature_specs.feature_ids), 2)
                                ),
                                model.net.NextScopedBlob(
                                    name + '_' + field + '_ranges')
                            ),
                         ),
                        ('values', input_record[field].values.items),
                    )
                ))
            else:
                raise TypeError(
                    "Unsupported input type: {0}".
                    format(feature_specs.feature_type))

        # TODO(amalevich): This schema is producing ranges. And thus if there is
        # something using it it should support ranges as well. It might be
        # confusing, if we don't add better support for ranges/have it as a
        # first layer
        self.output_schema = schema.Struct(
            *outputs
        )

        # TODO(amalevich): Consider moving this data to schema, instead
        # Structs doens't support attaching metadata to them and clonning
        # will break things badly, but this is the most elegant way to pass
        # this info around. Should we change it or it'll be too much work and
        # not worse it?
        for field, feature_specs in input_specs:
            schema.attach_metadata_to_scalars(
                self.output_schema[field],
                schema.Metadata(
                    feature_specs=feature_specs)
            )
        self.zero = model.global_constants['ZERO']
        self.zero_range = model.global_constants['ZERO_RANGE']

    # Add operators to all types that need to be densified
    def add_ops(self, net):
        record = self.input_record
        for field, feature_specs in self.input_specs:
            if feature_specs.feature_type == 'FLOAT':
                net.SparseToDenseMask(
                    [
                        record[field].keys(),
                        record[field].values(),
                        self.zero,
                        record[field].lengths(),
                    ],
                    [
                        self.output_schema[field](),
                    ],
                    mask=feature_specs.feature_ids,
                )
            elif feature_specs.feature_type == 'ID_LIST':
                id_list_ranges = net.LengthsToRanges(
                    record[field].values.lengths(),
                    net.NextScopedBlob('id_list_ranges')
                )
                net.SparseToDenseMask(
                    [
                        record[field].keys(), id_list_ranges, self.zero_range,
                        record[field].lengths()
                    ],
                    self.output_schema[field].ranges(),
                    mask=feature_specs.feature_ids,
                )

    def get_metadata(self):
        metadata = []
        for field, feature_specs in self.input_specs:
            metadata.append(
                (
                    {
                        'type': feature_specs.feature_type,
                        'names': feature_specs.feature_names,
                        'ids': feature_specs.feature_ids,
                    },
                    self.output_schema[field].field_blobs(),
                    self.output_schema[field].field_types()
                )
            )
            if feature_specs.feature_type == 'FLOAT':
                metadata[-1][0]['cardinality'] = 1
        return metadata
