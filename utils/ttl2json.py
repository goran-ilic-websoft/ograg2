"""
This script converts a Turtle (.ttl) RDF ontology file to a compact, single-language JSON-LD file.
It:
- Extracts all RDF prefixes and adds them to the @context (including auto-generated ones for unknown bases).
- Shortens all IRIs in keys and values using the prefixes.
- Keeps only literal values for the selected language (as plain strings).
- Sets the default language in @context.
Usage: Adjust the file paths and language at the bottom of the script.
"""

from rdflib import Graph
import json
import re

def extract_base_iri(iri):
    m = re.match(r"(.+[#/])[^#/]+$", iri)
    return m.group(1) if m else None

def filter_lang_fields_single(node, lang):
    # Zadrži samo literalna polja za dati jezik, i literal kao string
    new_node = {}
    for k, v in node.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "@language" in v[0]:
            filtered = [item["@value"] for item in v if item.get("@language") == lang]
            if filtered:
                # Ako ima samo jedan, koristi string, inače listu stringova
                new_node[k] = filtered[0] if len(filtered) == 1 else filtered
        elif isinstance(v, dict) and "@language" in v:
            if v.get("@language") == lang:
                new_node[k] = v["@value"]
        else:
            new_node[k] = v
    return new_node

def ttl_to_jsonld_one_lang(ttl_path, jsonld_path, lang="en"):
    g = Graph()
    g.parse(ttl_path, format="ttl")
    jsonld_str = g.serialize(format="json-ld", indent=2)
    data = json.loads(jsonld_str)

    # Pripremi mapu prefiksa iz rdflib
    prefix_map = {prefix: str(ns) for prefix, ns in g.namespaces()}
    used_bases = set(prefix_map.values())

    # Pronađi @graph
    if isinstance(data, dict):
        graph = data.get("@graph", [])
    elif isinstance(data, list):
        graph = data
    else:
        graph = []

    # Pronađi sve baze koje nisu u prefix_map
    all_iris = set()
    def collect_iris(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.startswith("http"):
                    all_iris.add(k)
                if isinstance(v, str) and v.startswith("http"):
                    all_iris.add(v)
                elif isinstance(v, list) or isinstance(v, dict):
                    collect_iris(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_iris(item)
    collect_iris(graph)

    missing_bases = set()
    for iri in all_iris:
        base = extract_base_iri(iri)
        if base and base not in used_bases:
            missing_bases.add(base)

    ns_counter = 1
    for base in sorted(missing_bases):
        prefix = f"ns{ns_counter}"
        while prefix in prefix_map:
            ns_counter += 1
            prefix = f"ns{ns_counter}"
        prefix_map[prefix] = base
        used_bases.add(base)
        ns_counter += 1

    def shorten_iri(iri, prefix_map):
        for prefix, ns in prefix_map.items():
            if iri.startswith(ns):
                return iri.replace(ns, f"{prefix}:")
        return iri

    def shorten_keys(obj, prefix_map):
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                new_k = shorten_iri(k, prefix_map) if isinstance(k, str) and k.startswith("http") else k
                if isinstance(v, str) and v.startswith("http"):
                    new_obj[new_k] = shorten_iri(v, prefix_map)
                elif isinstance(v, list):
                    new_obj[new_k] = [
                        shorten_iri(item, prefix_map) if isinstance(item, str) and item.startswith("http")
                        else shorten_keys(item, prefix_map)
                        for item in v
                    ]
                elif isinstance(v, dict):
                    new_obj[new_k] = shorten_keys(v, prefix_map)
                else:
                    new_obj[new_k] = v
            return new_obj
        elif isinstance(obj, list):
            return [
                shorten_iri(item, prefix_map) if isinstance(item, str) and item.startswith("http")
                else shorten_keys(item, prefix_map)
                for item in obj
            ]
        else:
            return obj

    # Skrati IRI-jeve
    short_graph = [shorten_keys(node, prefix_map) for node in graph]
    # Zadrži samo jedan jezik i literal kao string
    single_lang_graph = [filter_lang_fields_single(node, lang) for node in short_graph]

    # Dodaj default language u context
    prefix_map["@language"] = lang

    with open(jsonld_path, "w", encoding="utf-8") as f:
        json.dump({"@context": prefix_map, "@graph": single_lang_graph}, f, ensure_ascii=False, separators=(",", ": "))

# Primer upotrebe:
ttl_to_jsonld_one_lang(
    "data/csv/pz_0.0.1.ttl",
    "data/ontology/pz_0.0.1_en_single.json",
    lang="en"
)