import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path

def process_dataset(base_folder: str, destination: str) -> None:
    """Metodo lanzadera para procesar cada uno de los datasets a nivel individual.
        Queremos generar graficos con un color diferente para cada tipo de ataque, y que en caso de que ese tipo de ataque se repita
        entre csvs, que el color sea el mismo por lo que utilizaremos un diccionario"""


    print("Recopilando los ataques del CIC-BCCC-NRC-TabularIoT-2024\n")
    all_attacks = get_all_attack_types(base_folder) # Lista con todos los ataques del dataset
    colors = generate_extended_colors(len(all_attacks)) # Genera ncolors, uno diferente para cada tipo de ataque

    attack_colors = dict(zip(all_attacks, colors)) # {ataque:color}

    # Procesar cada dataset
    for subfolder in sorted(os.listdir(base_folder)):
        process_single_dataset(base_folder, subfolder, attack_colors, destination)


def get_all_attack_types(base_folder: str) -> set[str]:
    """Metodo para saber que tipos de ataque hay en cada dataset."""
    all_attacks = set()
    for subfolder in sorted(os.listdir(base_folder)):
        dataset_path = os.path.join(base_folder, subfolder)
        csv_files = glob.glob(os.path.join(dataset_path, "*.csv"))

        for csv_file in csv_files:
            df_temp = pd.read_csv(csv_file, nrows= 1)
            all_attacks.update(df_temp[df_temp['Label'] != 0]['Attack Name'].astype(str).unique())
            del df_temp

    print(f"En el dataset se presentan n: {len(all_attacks)} ataques diferentes\n")
    print(f"En el dataset se presentan los siguientes tipos de ataque: {all_attacks}\n")
    return all_attacks



def generate_extended_colors(n_attacks: int) -> np.ndarray:
    """Metodo para generar un conjunto de colores mas amplio, ya que disponemos de 40* (tras eliminar los que no son TCP) tipos de ataque no nos sirve con una unica paleta."""
    colormaps = [
        plt.colormaps['tab20'](np.linspace(0, 1, 20)),
        plt.colormaps['Set3'](np.linspace(0, 1, 12)),
        plt.colormaps['Set2'](np.linspace(0, 1, 8)),
        plt.colormaps['Paired'](np.linspace(0, 1, 12))
    ]

    all_colors = np.vstack(colormaps)

    # En caso de que introdujesemos mas ataques al dataset o no fuesen suficientes
    if n_attacks > len(all_colors):
        additional_colors = plt.colormaps['hsv'](np.linspace(0, 1, n_attacks - len(all_colors)))
        all_colors = np.vstack([all_colors, additional_colors])

    np.random.shuffle(all_colors)
    return all_colors

def process_single_dataset(base_folder, subfolder: str, attack_colors, destination: str) -> None:
    """El CIC-BCCC-ACI-IOT-2023, esta compuesto por 9 datasets, por lo que es interesante obtener informacion
       a nivel individual de cada uno de ellos. Metodo lanzadera para cada dataset."""

    dataset_path = os.path.join(base_folder, subfolder)
    csv_files = glob.glob(os.path.join(dataset_path, "*.csv"))

    dataframes = []
    for csv_file in csv_files:
        df_temp = pd.read_csv(csv_file)
        dataframes.append(df_temp)

    # Creamos un df con todos los csv de un unico dataset
    df_subfolder = pd.concat(dataframes)

    # Ejecucion de cada parte del analisis
    write_dataset_info(df_subfolder, subfolder, destination) # Informacion general en formato txt

    # Generamos graficas para determinar la distribucion de atributos categoricos
    plot_label_distribution(df_subfolder, subfolder, destination) # Distribucion del tipo de trafico de cada dataset (1 = malicioso 0 = benigno)
    plot_attack_distribution(df_subfolder, subfolder,attack_colors, destination) # Distribucion del tipo de ataque dentro de cada dataset
    if destination == "processed":
            plot_service_attacked(df_subfolder, subfolder, destination) # Distribucion del tipo de servicio (puerto) accedido en cada dataset

    # Distribucion del resto de atributos numericos
    plot_numerical_attributes_distribution(df_subfolder, subfolder, destination)



def write_dataset_info(df: pd.DataFrame, subfolder: str, destination) -> None:
    """Vamos a guardar informacion individual de cada dataset en un txt, numero de filas, numero de filas duplicadas,
       distribucion de Label (tambien se hara mas adelante una grafica), valores nulos dentro del dataset y distribucion
       de los tipos de ataque presentes en el dataset. Tambien vamos a analizar para cada variable numerica sus outliers (POR IMPLEMENTAR)"""

    # Creamos un archivo txt con el nombre del dataset para escribir
    file_path = f'../analysis/text/{destination}/{subfolder}_analysis.txt'
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        pd.options.display.min_rows = 100
        def write_to_file(text):
            f.write(str(text) + '\n')

        write_to_file("\n" + "#" * 50)
        write_to_file(f"INFORMACION DEL DATASET: {subfolder}")
        write_to_file(f"#" * 50)

        # Info del dataset
        df.info(buf=f)

        # Información básica
        write_to_file(f"\nNumero total de filas: {df.shape[0]}")
        write_to_file(f"Numero de filas duplicadas: {df.duplicated().sum()}")

        # Análisis de valores nulos
        columns_with_nulls = df.columns[df.isnull().any()].tolist()
        if columns_with_nulls :
            write_to_file(f"\nAtributos con valores nulos: {columns_with_nulls}")
            rows_with_nulls = df.isnull().any(axis=1).sum()
            write_to_file(f"\nFilas con valores nulos: {rows_with_nulls}")
        else:
            write_to_file("No hay atributos con valores nulos\n")

        # Análisis de valores negativos
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns # Filtramos solo para columnas numericas
        sum_rows_with_negatives = df[numeric_cols].lt(0).any(axis=1).sum()
        write_to_file(f"Numero de filas con valores negativos: {sum_rows_with_negatives}")

        if sum_rows_with_negatives > 0:
            df_negative_mask = df[numeric_cols] < 0
            negative_columns = numeric_cols[df_negative_mask.any()]
            write_to_file(f"Los atributos que tienen valores negativos son {list(negative_columns)}: \n")
            del df_negative_mask

        ### ANALISIS DE LOS ATRIBUTOS DEL DATASET PARA VER QUE VALORES TIENEN


        """ESTADISTICAS DE LOS FLUJOS"""
        flow_cols = ['Flow Duration', 'Total Fwd Packet', 'Total Bwd packets', 'Flow Bytes/s', 'Flow Packets/s']
        write_to_file("\nEstadisticas de los fluijos TCP:")
        write_to_file("-" * 30)
        write_to_file(df[flow_cols].describe().to_string())

        """ESTADISTICAS DE LOS PAQUETES"""
        packet_cols = ['Packet Length Min', 'Packet Length Max', 'Packet Length Mean', 'Packet Length Std', 'Packet Length Variance', 'Average Packet Size', 'Fwd Act Data Pkts']
        packet_cols_f = ['Total Length of Fwd Packet', 'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std', 'Fwd Packets/s']
        packet_cols_b = ['Total Length of Bwd Packet', 'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean', 'Bwd Packet Length Std','Bwd Packets/s']

        write_to_file("\nEstadisticas de paquetes TCP:")
        write_to_file(df[packet_cols].describe().to_string())
        write_to_file("\nEstadisticas de paquetes TCP (Forward):")
        write_to_file(df[packet_cols_f].describe().to_string())
        write_to_file("\n+ Estadisticas de paquetes TCP (Backward):")
        write_to_file(df[packet_cols_b].describe().to_string())
        write_to_file("-" * 30)

        """ESTADISTICAS DE LAS CABECERAS"""
        header_cols = ['Fwd Header Length', 'Bwd Header Length']
        write_to_file("\nEstadisticas de las cabeceras de los paquetes:")
        write_to_file(df[header_cols].describe().to_string())

        """ESTADISTICAS DE FLAGS"""
        flag_cols = ['FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count', 'ACK Flag Count', 'URG Flag Count',
                     'CWR Flag Count', 'ECE Flag Count']
        flag_cols_f = ['Fwd PSH Flags', 'Fwd URG Flags']
        flag_cols_b = ['Bwd PSH Flags', 'Bwd URG Flags']

        write_to_file("\nEstadisticas de las flags de los paquetes:")
        write_to_file(df[flag_cols].describe().to_string())
        write_to_file("\nEstadisticas de las flags de los paquetes (Forward):")
        write_to_file(df[flag_cols_f].describe().to_string())
        write_to_file("\nEstadisticas de las flags de los paquetes (Backward):")
        write_to_file(df[flag_cols_b].describe().to_string())
        write_to_file("-" * 30)

        """ESTADISTICAS IAT (Inter Arrival Time)"""
        iat_cols = ['Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Mean', 'Fwd IAT Std']
        iat_cols2 = ['Bwd IAT Max', 'Bwd IAT Min', 'Bwd IAT Mean', 'Bwd IAT Std']

        write_to_file("\nEstadisticas de Inter Arrival Time:")
        write_to_file(df[iat_cols].describe().to_string())
        write_to_file("\nEstadisticas de Inter Arrival Time 2:")
        write_to_file(df[iat_cols2].describe().to_string())
        write_to_file("-" * 30)

        """ESTADISTICAS DE LA VENTANA"""
        # CANTIDAD DE DATOS QUE EL DESPOSITIVO DE DESTINO VA A PODER PROCESAR
        window_cols = ['FWD Init Win Bytes', 'Bwd Init Win Bytes']
        write_to_file("\nEstadisticas del tamaño de ventana:")
        write_to_file("-" * 30)
        write_to_file(df[window_cols].describe().to_string())

        """ESTADISTICAS DE ACTIVIDAD"""
        activity_cols = ['Active Mean', 'Active Std', 'Active Max', 'Active Min',
                         'Idle Mean', 'Idle Std', 'Idle Max', 'Idle Min','Down/Up Ratio']
        write_to_file("\nEstadisticas de actividad del flujo:")
        write_to_file("-" * 30)
        write_to_file(df[activity_cols].describe().to_string())

        """ESTADISTICAS DE SEGMENTO"""
        segment_cols = ['Fwd Segment Size Avg', 'Bwd Segment Size Avg', 'Fwd Seg Size Min']
        write_to_file("\nEstadisticas de segmento:")
        write_to_file("-" * 30)
        write_to_file(df[segment_cols].describe().to_string())

        """ESTADISTICAS DE TRANSMISION EN BLOQUES (RAFAGAS)"""
        bulk_cols = ['Fwd Bytes/Bulk Avg', 'Fwd Packet/Bulk Avg', 'Fwd Bulk Rate Avg', 'Bwd Bytes/Bulk Avg', 'Bwd Packet/Bulk Avg', 'Bwd Bulk Rate Avg']
        write_to_file("\nEstadisticas de rafagas de transmision:")
        write_to_file("-" * 30)
        write_to_file(df[bulk_cols].describe().to_string())

        """ESTADISTICAS DE SUBFLOWS"""
        subflow_cols = ['Subflow Fwd Packets', 'Subflow Bwd Packets', 'Subflow Fwd Bytes', 'Subflow Bwd Bytes']
        write_to_file("\nEstadisticas de los sub-flujos:")
        write_to_file("-" * 30)
        write_to_file(df[subflow_cols].describe().to_string())

        # Al analizar cuales eran las correlaciones entre atributos se ha visto que hay atributos que tienen 0 en todas sus  filas! En todos los datasets
        # Por lo que parece que CICFlowMeter no recoge bien esta informacion
        """ESTADISTICAS DE ATRIBUTOS CON VALORES EXTRAÑOS"""
        atributos_extraños = ["Bwd PSH Flags", "Bwd URG Flags", "Fwd Bytes/Bulk Avg",
                            "Fwd Packet/Bulk Avg", "Fwd Bulk Rate Avg"]
        write_to_file("\nEstadisticas de los flujos anormales (Todos los valores son 0):")
        write_to_file("-" * 30)
        write_to_file(df[atributos_extraños].describe().to_string())

        # Distribución de etiquetas
        write_to_file("\nDistribucion del tipo de trafico en el dataset:")
        write_to_file(df["Label"].value_counts(dropna=False).to_string())
        write_to_file("\nDistribucion del tipo de ataque en el dataset:")
        write_to_file(df["Attack Name"].value_counts(dropna=False).to_string())

        write_to_file("\nPuertos de destino más frecuentes:")
        write_to_file("-" * 30)

        if destination == "raw": # Column doesnt exist in the processed dataset
            if 'Dst Port' in df.columns:
                top_ports = df['Dst Port'].value_counts().head(20)  # Top 20 más comunes
                write_to_file(top_ports.to_string())
            else:
                write_to_file("No se encontró la columna 'Dst Port'.")
            write_to_file("\n" + "#" * 50 + "\n")

    print(f"Analysis guardado en: analysis/{subfolder}_analysis.txt")



def plot_label_distribution(df: pd.DataFrame, subfolder: str, destination: str) -> None:
    """Metodo para generar un grafico sobre la distribucion del atributo Label (tipo de conexión)."""

    carpeta_proyecto = Path(__file__).resolve().parent.parent
    target_path = carpeta_proyecto / "analysis"/ "diagrams"/ destination / subfolder
    os.makedirs(target_path, exist_ok=True)

    plt.figure(figsize=(10, 6))
    counts = df['Label'].value_counts() # Numero de ocurrencias de trafico benigno y malicioso
    colors = ['red','green']

    ax = counts.plot(kind='bar', color=colors)
    plt.title(f"Distribucion de la etiqueta de clase en {subfolder}")
    plt.xlabel("Tipo de conexion (1 = malicioso, 0 = benigno)")
    plt.ylabel("Frecuencia")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.xticks(rotation=0)
    plt.tight_layout()

    filename = "Tipo_de_trafico.png"
    filepath = os.path.join(target_path, filename)
    plt.savefig(filepath)
    plt.close()


def plot_attack_distribution(df: pd.DataFrame, subfolder: str, attack_colors, destination) -> None:
    """Metodo para generar un grafico sobre la distribucion del atributo "Tipo de Ataque"."""

    carpeta_proyecto = Path(__file__).resolve().parent.parent
    target_path = carpeta_proyecto / "analysis"/ "diagrams"/ destination / subfolder
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    df_attacks = df[df['Label'] != 0]
    counts = df_attacks['Attack Name'].value_counts()
    current_colors = [attack_colors[attack] for attack in counts.index]

    plt.figure(figsize=(10, 6))
    ax = counts.plot(kind='bar', color=current_colors, width=0.8)
    plt.title(f"Attack Type Distribution in {subfolder}")
    plt.xlabel("Attack Type")
    plt.ylabel("Frequency")
    plt.xticks(rotation=45, ha='right')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.tight_layout()

    filename = "Tipo_de_ataque.png"
    filepath = os.path.join(target_path, filename)
    plt.savefig(filepath)
    del df_attacks
    plt.close()


def plot_service_attacked(df: pd.DataFrame, subfolder: str, destination) -> None:
    """Metodo para generar un grafico sobre la distribucion del atributo "Tipo de Ataque"."""

    carpeta_proyecto = Path(__file__).resolve().parent.parent
    target_path = carpeta_proyecto / "analysis"/ "diagrams"/ destination / subfolder
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    df_attacks = df[df['Label'] != 0]
    counts = df_attacks['Service'].value_counts()

    plt.figure(figsize=(10, 6))
    ax = counts.plot(kind='bar', width=0.8)
    plt.title(f"Service distribution in {subfolder}")
    plt.xlabel("Service")
    plt.ylabel("Frequency")
    plt.xticks(rotation=45, ha='right')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.tight_layout()

    filename = "Tipo_de_servicio.png"
    filepath = os.path.join(target_path, filename)
    plt.savefig(filepath)
    plt.close()


def plot_numerical_attributes_distribution(df: pd.DataFrame, subfolder: str, destination) -> None:

    carpeta_proyecto = Path(__file__).resolve().parent.parent
    target_path = carpeta_proyecto / "analysis"/ "diagrams"/ destination / subfolder
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    sample_size = min(1000000,len(df))
    sample_df = df.sample(sample_size, random_state = 42)

    df_numeric = sample_df.select_dtypes(include=["float64", "int64"])
    for col in df_numeric.columns:
        plt.figure(figsize=(15, 4))

        # Elaboracion del histograma y configuracion de sus caracteristicas
        plt.subplot(1, 2, 1)
        df_numeric[col].hist(grid=False, color="royalblue", edgecolor="black")
        plt.title(f"Histograma de {col}")
        plt.ylabel("Count")
        plt.ticklabel_format(style='plain', axis='x') # Eliminar la notacion científica

        plt.subplot(1, 2, 2)
        sns.boxplot(x=df_numeric[col], width=0.5, showmeans=True,
                    meanprops={"marker":"o", "markerfacecolor":"white", "markeredgecolor":"royalblue", "markersize":"10"},
                    flierprops={"marker":"D", "markerfacecolor":"royalblue", "markeredgecolor":"black", "markersize":"5"},
                    medianprops={"color": "royalblue"},
                    boxprops={"facecolor": "skyblue", "edgecolor": "black"},
                    whiskerprops={"color": "black", "linestyle": "--"})

        plt.title(f"Distribucion de {col} en {subfolder}")
        plt.ticklabel_format(style='plain', axis='x')

        valid_col_name = col.replace("/", "_").replace("\\", "_") # Para el atributo Flow Bytes/s por el tema de la barra en el path de windows
        filename = f"{valid_col_name}.png"

        filepath = os.path.join(target_path, filename)

        plt.savefig(filepath)
        plt.close()

    print(f"Guardados los diagramas para {subfolder}")


def main():
    project_folder = Path(__file__).resolve().parent.parent

    raw_dataframe = project_folder / "data" / "raw" / "CIC-BCCC-NRC-TabularIoT-2024"
    processed_dataframe = project_folder / "data" / "processed" / "CIC-BCCC-NRC-TabularIoT-2024"

    # Solo evaluar el dataset ya procesado, en caso contrario explota ya que hay csv que en el campo 'Date' tienen diferente formato
    process_dataset(raw_dataframe, "raw")
    # process_dataset(processed_dataframe, "processed")

if __name__ == "__main__":
    main()
