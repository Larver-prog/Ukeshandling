import streamlit as st
import pandas as pd
import random
import aiohttp
import anyio
import os
from bring_api import Bring

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
# Send shopping list to Bring (anyio)
# -------------------------------
def send_shopping_list_to_bring(shopping_list, bring_lists, email, password, list_name):
    async def send():
        async with aiohttp.ClientSession() as session:
            bring = Bring(session, email, password)
            await bring.login()
            selected_list = next(lst for lst in bring_lists if lst.name == list_name)
            for _, row in shopping_list.iterrows():
                await bring.save_item(selected_list.listUuid, row["Ingrediens"], f"{row['Antall']} {row['Enhet']}")
            st.success(f"✅ Handlelisten ble lagt til i Bring-listen: {list_name}")

    anyio.run(send)

# -------------------------------
# Streamlit app
# -------------------------------
st.title("🍽️ Ukesmeny generator")

# -------------------------------
# Placeholders for menu and shopping list
# -------------------------------
menu_placeholder = st.empty()
shopping_placeholder = st.empty()

# -------------------------------
# Load Excel
# -------------------------------
default_file_path = "Data/Ukes meny.xlsx"
uploaded_file = st.file_uploader("Last opp Excel med oppskrifter (valgfritt)", type=["xlsx"])

if uploaded_file:
    recipes = load_data(uploaded_file)
elif os.path.exists(default_file_path):
    recipes = load_data(default_file_path)
    st.info(f"Bruker standard Excel-fil: {default_file_path}")
else:
    recipes = None
    st.warning("Ingen Excel-fil funnet. Last opp en fil for å fortsette.")

if recipes is not None:
    # -------------------------------
    # Load persisted Ukesmeny & shopping list
    # -------------------------------
    df_menu = st.session_state.get("ukesmeny", None)
    shopping_list = st.session_state.get("shopping_list", None)

    if df_menu is not None:
        menu_placeholder.table(df_menu)
    if shopping_list is not None:
        shopping_placeholder.dataframe(shopping_list)

    # -------------------------------
    # Menu generation
    # -------------------------------
    mode = st.radio("Hvordan vil du lage menyen?", ["🎲 Tilfeldig meny", "✅ Velg retter selv"])

    if mode == "🎲 Tilfeldig meny":
        n_days = st.slider("Hvor mange middager vil du planlegge?", 1, 7, 5)
        if st.button("Generer meny"):
            available_dishes = recipes["Middagsrett"].unique().tolist()
            menu = random.sample(available_dishes, n_days)

            df_menu = pd.DataFrame({"Dag": range(1, n_days+1), "Middagsrett": menu})
            shopping_list = build_shopping_list(menu, recipes)

            st.session_state["ukesmeny"] = df_menu
            st.session_state["shopping_list"] = shopping_list

            menu_placeholder.table(df_menu)
            shopping_placeholder.dataframe(shopping_list)

    elif mode == "✅ Velg retter selv":
        available_dishes = recipes["Middagsrett"].unique().tolist()
        chosen = st.multiselect("Velg retter:", available_dishes)

        if chosen:
            df_menu = pd.DataFrame({"Dag": range(1, len(chosen)+1), "Rett": chosen})
            shopping_list = build_shopping_list(chosen, recipes)

            st.session_state["ukesmeny"] = df_menu
            st.session_state["shopping_list"] = shopping_list

            menu_placeholder.table(df_menu)
            shopping_placeholder.dataframe(shopping_list)

# -------------------------------
# Export Excel if menu exists
# -------------------------------
if "ukesmeny" in st.session_state and "shopping_list" in st.session_state:
    df_menu = st.session_state["ukesmeny"]
    shopping_list = st.session_state["shopping_list"]

    with pd.ExcelWriter("ukemeny.xlsx", engine="openpyxl") as writer:
        df_menu.to_excel(writer, sheet_name="Meny", index=False)
        shopping_list.to_excel(writer, sheet_name="Handleliste", index=False)

    with open("ukemeny.xlsx", "rb") as f:
        st.download_button("⬇️ Last ned meny + handleliste (Excel)", f, "ukemeny.xlsx")

# -------------------------------
# Bring! login section
# -------------------------------
st.subheader("🔗 Bring!-integrasjon")

if "show_login" not in st.session_state:
    st.session_state.show_login = False

if st.button("Koble til Bring!"):
    st.session_state.show_login = True

if st.session_state.show_login:
    with st.form("bring_login_form"):
        email = st.text_input("E-post")
        password = st.text_input("Passord", type="password")
        submit = st.form_submit_button("Logg inn")

        if submit:
            async def login_bring():
                async with aiohttp.ClientSession() as session:
                    bring = Bring(session, email, password)
                    await bring.login()
                    lists = (await bring.load_lists()).lists
                    st.session_state.bring_lists = lists
                    st.session_state.bring_email = email
                    st.session_state.bring_password = password
                    st.success("✅ Tilkoblet Bring!")

            anyio.run(login_bring)

# -------------------------------
# Send to Bring! section
# -------------------------------
if "bring_lists" in st.session_state and "shopping_list" in st.session_state:
    shopping_list = st.session_state["shopping_list"]
    st.subheader("📲 Send handleliste til Bring!")

    list_names = [lst.name for lst in st.session_state.bring_lists]
    choice = st.selectbox("Velg en liste:", list_names)

    if st.button("📲 Send til valgt Bring-liste"):
        send_shopping_list_to_bring(
            shopping_list,
            st.session_state.bring_lists,
            st.session_state.bring_email,
            st.session_state.bring_password,
            choice
        )
