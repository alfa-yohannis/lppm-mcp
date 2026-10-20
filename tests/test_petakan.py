"""Uji pemetaan halaman: struktur form tercatat, nilai rahasia tidak."""

from __future__ import annotations

import json

from lppm_mcp.halaman import Halaman
from lppm_mcp.petakan_form import nama_berkas_peta, petakan_halaman
from conftest import PORTAL, TOKEN_UJI, halaman_login, halaman_penelitian

HALAMAN_AJAX = """<html><body><div class="content-wrapper"><h1>Pengabdian</h1>
<table id="tabel-pkm"><thead><tr><th>Judul</th><th>Mitra</th></tr></thead><tbody></tbody></table>
</div>
<script>
$('#tabel-pkm').DataTable({ processing: true, serverSide: true, ajax: '/pengabdian/data' });
$.ajax({ url: "/pengabdian/statistik", type: "GET" });
</script></body></html>"""


def test_peta_form_login_tanpa_token_dan_sandi():
    peta = petakan_halaman(Halaman(url=f"{PORTAL}/login", html=halaman_login(TOKEN_UJI)))

    form = peta["form"][0]
    assert form["method"] == "POST"
    assert form["action"] == f"{PORTAL}/login"
    isian = {satu["name"]: satu for satu in form["field"]}
    assert isian["_token"]["value"] == "<disamarkan>"
    assert isian["login"]["label"] == "NIDN atau Email Address"
    assert isian["login"]["wajib"] is True
    assert TOKEN_UJI not in json.dumps(peta)


def test_peta_menemukan_endpoint_ajax_datatables():
    peta = petakan_halaman(Halaman(url=f"{PORTAL}/pengabdian", html=HALAMAN_AJAX))

    assert peta["datatables"] is True
    assert peta["endpoint_ajax"] == ["/pengabdian/data", "/pengabdian/statistik"]
    assert peta["tabel"] == [{"nomor": 1, "judul": "Pengabdian", "kolom": ["Judul", "Mitra"], "jumlah_baris": 0}]


def test_peta_mencatat_tautan_isi():
    peta = petakan_halaman(Halaman(url=f"{PORTAL}/penelitian", html=halaman_penelitian(1)))

    assert {"teks": "Detail", "url": f"{PORTAL}/penelitian/102"} in peta["tautan_isi"]


def test_nama_berkas_peta_aman_untuk_sistem_berkas():
    assert nama_berkas_peta("/penelitian/create?tahun=2026") == "form_penelitian_create_tahun_2026.json"
    assert nama_berkas_peta("/") == "form_beranda.json"
    assert nama_berkas_peta(f"{PORTAL}/pkm") == "form_lppm_pradita_ac_id_pkm.json"
