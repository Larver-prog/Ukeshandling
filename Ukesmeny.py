import streamlit as st
import pandas as pd
import random

# -------------------------------
# Load recipe data from Excel
# -------------------------------
@st.cache_data
def load_data(file_path):
    xls = pd.ExcelFile(file_path)
    recipes = []
    for sheet in ["Kjøtt", "Fisk", "Vegetar"]:
        if sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["Kategori"] = sheet
            recipes.append(df)
    return pd.concat(recipes, ignore_index=True)

# -------------------------------
# Build shopping list
# -------------------------------
def build_shopping_list(menu, recipes):
    shopping = []
    for rett in menu:
        ingreds = recipes[recipes["Middagsrett"] == rett][["Ingrediens", "Antall", "Enhet"]]
        shopping.append(ingreds)
    if shopping:
        shopping_df = pd.concat(shopping)
        shopping_sum = (
            shopping_df.groupby(["Ingrediens", "Enhet"], as_index=False)
            .agg({"Antall": "sum"})
            .sort_values("Ingrediens")
        )
        return shopping_sum
    return pd.DataFrame(columns=["Ingrediens", "Antall", "Enhet"])

# -------------------------------
# Streamlit app
# -------------------------------
st.title("🍽️ Ukesmeny generator")

uploaded_file = st.file_uploader("Last opp Excel med oppskrifter", type=["xlsx"])

if uploaded_file:
    recipes = load_data(uploaded_file)

    #st.subheader("📖 Oppskrifter")
    #st.dataframe(recipes.head())

    # Choose mode: random or manual
    mode = st.radio("Hvordan vil du lage menyen?", ["🎲 Tilfeldig meny", "✅ Velg retter selv"])

    if mode == "🎲 Tilfeldig meny":
        n_days = st.slider("Hvor mange middager vil du planlegge?", 1, 7, 5)
        if st.button("Generer meny"):
            available_dishes = recipes["Middagsrett"].unique().tolist()
            menu = random.sample(available_dishes, n_days)

            st.subheader("📅 Ukemeny")
            df_menu = pd.DataFrame({"Dag": range(1, n_days+1), "Middagsrett": menu})
            st.table(df_menu)

            shopping_list = build_shopping_list(menu, recipes)
            st.subheader("🛒 Handleliste")
            st.dataframe(shopping_list)

            # Export
            with pd.ExcelWriter("ukemeny.xlsx", engine="openpyxl") as writer:
                df_menu.to_excel(writer, sheet_name="Meny", index=False)
                shopping_list.to_excel(writer, sheet_name="Handleliste", index=False)

            with open("ukemeny.xlsx", "rb") as f:
                st.download_button("⬇️ Last ned meny + handleliste (Excel)", f, "ukemeny.xlsx")

    elif mode == "✅ Velg retter selv":
        available_dishes = recipes["Middagsrett"].unique().tolist()
        chosen = st.multiselect("Velg retter:", available_dishes)

        if chosen:
            st.subheader("📅 Din meny")
            df_menu = pd.DataFrame({"Dag": range(1, len(chosen)+1), "Rett": chosen})
            st.table(df_menu)

            shopping_list = build_shopping_list(chosen, recipes)
            st.subheader("🛒 Handleliste")
            st.dataframe(shopping_list)

            # Export
            with pd.ExcelWriter("ukemeny.xlsx", engine="openpyxl") as writer:
                df_menu.to_excel(writer, sheet_name="Meny", index=False)
                shopping_list.to_excel(writer, sheet_name="Handleliste", index=False)

            with open("ukemeny.xlsx", "rb") as f:
                st.download_button("⬇️ Last ned meny + handleliste (Excel)", f, "ukemeny.xlsx")

else:
    st.info("Last opp en Excel-fil med arkene Kjøtt, Fisk, Vegetar (format: Rett, Ingrediens, Mengde, Enhet).")
