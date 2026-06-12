import streamlit as st
import pandas as pd

st.title("加库存整理工具")

inventory_file = st.file_uploader("上传库存表 CSV（决定排序顺序）", type="csv", key="inventory")
restock_file = st.file_uploader("上传加库存 CSV", type="csv", key="restock")

if inventory_file and restock_file:
    # --- Read inventory file ---
    inv_df = pd.read_csv(inventory_file)
    # SKU编码 format: NPJ005-S / NPJ005-M / NPJ005-L
    inv_df["base_SKU"] = inv_df["SKU编码"].str.replace(r"-(S|M|L)$", "", regex=True)
    inv_df["size"] = inv_df["SKU编码"].str.extract(r"-(S|M|L)$")

    # Build SKU -> name map from inventory
    inv_name_map = {}
    for _, row in inv_df.iterrows():
        sku = row["base_SKU"]
        name = row.get("产品名称", "")
        if sku not in inv_name_map and pd.notna(name) and str(name).strip():
            inv_name_map[sku] = str(name).strip()

    inventory_sku_set = set(inv_df["base_SKU"].dropna())

    # --- Read restock file ---
    restock_df = pd.read_csv(restock_file)

    # Build SKU -> name map from restock
    restock_name_map = (
        restock_df.drop_duplicates("SKU").set_index("SKU")["英文名称"].to_dict()
    )

    # Aggregate S/M/L per base SKU (handles duplicate rows)
    restock_agg = (
        restock_df.groupby("SKU", as_index=False)[["S数量", "M数量", "L数量"]].sum()
    )
    restock_map = restock_agg.set_index("SKU")[["S数量", "M数量", "L数量"]].to_dict("index")
    restock_sku_set = set(restock_map.keys())

    size_col = {"S": "S数量", "M": "M数量", "L": "L数量"}

    # --- Build result: one row per SKU-size line, matching inventory layout ---
    result_rows = []
    for _, inv_row in inv_df.iterrows():
        base = inv_row["base_SKU"]
        size = inv_row["size"]
        if pd.isna(size):
            continue
        if base in restock_map:
            qty = int(restock_map[base][size_col[size]])
        else:
            qty = 0
        result_rows.append({"SKU编码": inv_row["SKU编码"], "加库存数量": qty})

    result_df = pd.DataFrame(result_rows)

    st.subheader("整理结果（按库存表顺序）")
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    csv_bytes = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="下载结果 CSV",
        data=csv_bytes,
        file_name="加库存整理结果.csv",
        mime="text/csv",
    )

    # Copyable: just the quantity column, one number per line (matches inventory row order)
    copyable = "\n".join(str(r["加库存数量"]) for r in result_rows)
    st.subheader("📋 可直接复制粘贴的数量列")
    st.caption("全选复制后，直接粘贴进库存表对应列即可")
    st.text_area("", value=copyable, height=300, label_visibility="collapsed")

    # --- Check 1: SKUs in restock but not in inventory ---
    extra_skus = restock_sku_set - inventory_sku_set
    st.subheader("⚠️ 加库存中有、但库存表中没有的款式")
    if extra_skus:
        extra_rows = []
        for sku in sorted(extra_skus):
            name = restock_name_map.get(sku, "")
            d = restock_map[sku]
            extra_rows.append({
                "SKU": sku,
                "英文名称（加库存）": name,
                "S数量": int(d["S数量"]),
                "M数量": int(d["M数量"]),
                "L数量": int(d["L数量"]),
            })
        st.dataframe(pd.DataFrame(extra_rows), use_container_width=True, hide_index=True)
    else:
        st.success("无——加库存里的款式全部在库存表中")

    # --- Check 2: Name mismatch for same SKU ---
    mismatches = []
    for sku in inventory_sku_set & restock_sku_set:
        inv_name = inv_name_map.get(sku, "")
        restock_name = str(restock_name_map.get(sku, "")).strip()
        if inv_name and restock_name and inv_name.lower() != restock_name.lower():
            mismatches.append({
                "SKU": sku,
                "库存表名称": inv_name,
                "加库存名称": restock_name,
            })

    st.subheader("⚠️ 同一 SKU 但英文名称对不上的款式")
    if mismatches:
        st.dataframe(pd.DataFrame(mismatches), use_container_width=True, hide_index=True)
    else:
        st.success("无——所有 SKU 对应的英文名称一致")
