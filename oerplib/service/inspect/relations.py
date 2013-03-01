# -*- coding: utf-8 -*-

import pydot

from oerplib import error

COLORS = {
    'many2one': '#0E2548',
    'one2many': '#008200',
    'many2many': '#008200',
    'required': 'blue',
    'normal': 'black',
}

TPL_MODEL = """<
<table cellborder="0" cellpadding="0" cellspacing="0"
       border="1" bgcolor="white" height="100%%">
    <tr>
        <td border="0" bgcolor="#64629C" align="center" colspan="2">
            <font color="white">{name}</font>
        </td>
    </tr>
    {attrs}
</table>>"""

TPL_ATTR = """
<tr>
    <td align="left" border="0">- <font color="{color}">{name}</font>
    </td>
    <td align="left" border="0"><font color="{color}">{type_}</font>
    </td>
</tr>
"""


class Relations(object):
    """TODO"""
    def __init__(self, oerp, model, maxdepth=1, blacklist=None, whitelist=None,
                 rel_types=None):
        if blacklist and whitelist:
            raise error.InternalError(
                "'blacklist' and 'whitelist' parameters can not be set "
                "simultaneously")
                #"Blacklist and whitelist parameters can't be defined together.")
        self._oerp = oerp
        self._model = model
        self._obj = self._oerp.get(model)
        self._maxdepth = maxdepth
        self._blacklist = blacklist or []
        self._whitelist = whitelist or []
        self._rel_types = rel_types or ['many2one', 'one2many', 'many2many']
        self._graph = pydot.Dot(
            graph_type='digraph', overlap="scalexy", splines="true")
        self._relations = {}
        self._stack = {'o2m': {}, 'm2m': {}}
        # Add the main model to the whitelist
        #if self._model not in self._whitelist:
        #    self._whitelist.append(self._model)
        # Build and draw relations
        self._build_relations(self._obj, 0)
        self._draw_relations()

    def _build_relations(self, obj, depth):
        """Build all relations of `obj` recursively:
            - many2one
            - one2many (will be bound to the related many2one)
            - many2many (will be bound with the eventual many2many from the
              other side)
        """
        # Stop scanning when the maxdepth is reached, or when the data model
        # has already been scanned
        if depth > self._maxdepth or obj._name in self._relations:
            return
        # Avoid scanning twice the data model
        #if obj._name in self._relations:
        #    return
        # Skip blacklisted models
        if obj._name != self._model:
            if (self._whitelist and obj._name not in self._whitelist) \
                    or (self._blacklist and obj._name in self._blacklist):
                return
        # Scan relational fields of the data model
        depth += 1
        fields = obj.fields_get()
        if obj._name not in self._relations:
            self._relations[obj._name] = {
                'relations': {},
                'obj': obj,
                'fields': dict((k, v) for k, v in fields.iteritems()
                               if not v.get('relation')),
            }
        for name, data in fields.iteritems():
            if 'relation' in data and data['type'] in self._rel_types:
                rel = data['relation']
                # many2one
                if data['type'] == 'many2one':
                    # Check if related one2many fields have been registered
                    # for the current many2one relation
                    o2m_fields = obj._name in self._stack['o2m'] \
                        and rel in self._stack['o2m'][obj._name] \
                        and name in self._stack['o2m'][obj._name][rel] \
                        and self._stack['o2m'][obj._name][rel][name] \
                        or []
                    # Add the field
                    self._relations[obj._name]['relations'][name] = {
                        'type': 'many2one',
                        'relation': rel,
                        'name': name,
                        'o2m_fields': o2m_fields,
                    }
                # one2many
                elif data['type'] == 'one2many':
                    rel_f = data.get('relation_field', None)
                    if rel_f:
                        # Case where the related m2o field has already been
                        # registered
                        if rel in self._relations \
                                and rel_f in self._relations[rel]['relations']:
                            if name not in self._relations[rel]['relations'][rel_f]:
                                self._relations[rel]['relations'][rel_f]['o2m_fields'].append(name)
                        # Otherwise, we will process the field later
                        else:
                            if rel not in self._stack['o2m']:
                                self._stack['o2m'][rel] = {}
                            if obj._name not in self._stack['o2m'][rel]:
                                self._stack['o2m'][rel][obj._name] = {}
                            if rel_f not in self._stack['o2m'][rel][obj._name]:
                                self._stack['o2m'][rel][obj._name][rel_f] = []
                            self._stack['o2m'][rel][obj._name][rel_f].append(name)
                    else:
                        pass
                # many2many
                # TODO
                # Scan relations recursively
                rel_obj = self._oerp.get(rel)
                self._build_relations(rel_obj, depth)

    def _draw_relations(self):
        """Generate the graphic."""
        for model, data in self._relations.iteritems():
            node = (data['obj'], data['fields'])
            self._graph.add_node(self._create_node(*node))
            for name, data2 in data['relations'].iteritems():
                if data2['relation'] in self._relations:
                    rel_obj = self._relations[data2['relation']]['obj']
                    edge = (data['obj'], rel_obj, data2)
                    self._graph.add_edge(self._create_edge(*edge))

    def _create_node(self, obj, fields):
        attrs = []
        for k, v in fields.iteritems():
            color = v.get('required') and COLORS['required'] or COLORS['normal']
            attr = TPL_ATTR.format(
                name=k, color=color, type_=v['type'])
            attrs.append(attr)
        label = TPL_MODEL.format(name=obj._name, attrs=''.join(attrs))
        kwargs = {
            'margin': "0",
            'shape': "none",
            'label': label,
        }
        return pydot.Node(obj._name, **kwargs)

    def _create_edge(self, obj1, obj2, data):
        name_color = data.get('required') \
            and COLORS['required'] or COLORS[data['type']]
        label = "<<font color='{color}'>{name}</font>".format(
                color=name_color, name=data['name'])
        if data['type'] == 'many2one' and data['o2m_fields']:
            label = "{label} <font color='{color}'>({o2m})</font>".format(
                label=label,
                color=COLORS['one2many'],
                o2m=', '.join(data['o2m_fields']))
        #label = "%s>" % label
        label = label + ">"
        kwargs = {
            'label': label,
            'color': COLORS[data['type']],
            'fontcolor': COLORS[data['type']],
            'arrowhead': data['type'] == 'many2many' and 'none' or 'normal',
        }
        return pydot.Edge(obj1._name, obj2._name, **kwargs)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
