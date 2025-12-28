Documentação de Banco de Dados: GovTech MinerVersão do Schema: 1.0 (Gold)Banco de Dados: MySQLORM: SQLAlchemyDescrição: Estrutura de armazenamento para captura, processamento e análise de Diários Oficiais municipais visando inteligência de mercado e vendas governamentais.1. Visão Geral do Modelo (ER Diagram)O sistema utiliza um modelo relacional simples de 1 para N (One-to-Many).Um Diário Oficial (Arquivo PDF) pode conter múltiplas Oportunidades (Licitações, Contratos, Avisos).Snippet de códigoerDiagram
    DIARIOS ||--o{ OPORTUNIDADES : "contém"
    DIARIOS {
        int id PK
        string municipio
        date data_publicacao
        string codigo_origem "ID Externo"
        boolean processado
    }
    OPORTUNIDADES {
        int id PK
        int diario_id FK
        string status "Aberto/Contratado"
        string data_sessao "Data Limite"
        float valor
        string vencedor
    }
2. Dicionário de DadosTabela: diariosRepresenta o documento físico (arquivo) e seus metadados originais. É a fonte da verdade para auditoria e rastreabilidade.ColunaTipo SQLDescrição TécnicaImportância para o NegócioidINTEGERChave Primária (Auto Increment).Identificador único interno do sistema.municipioVARCHAR(100)Nome da cidade (ex: "Lençóis Paulista").Escalabilidade: Permite filtrar oportunidades por região geográfica quando o sistema cobrir múltiplas cidades.data_publicacaoDATEData de emissão do jornal oficial.Permite criar alertas diários ("O que saiu hoje?") e relatórios temporais.nome_arquivoVARCHAR(255)Nome do arquivo salvo localmente (ex: diario_1787.pdf).Auditoria e debug. Garante acesso ao arquivo físico se necessário.codigo_origemINTEGERID único do diário no sistema da Prefeitura.Vital: Usado para reconstruir o Link Oficial (A prova real para o usuário). Garante unicidade.numero_edicaoINTEGERNúmero sequencial da edição.Referência jurídica oficial para impugnações ou recursos administrativos.hash_origemVARCHAR(100)Hash MD5/SHA ou assinatura do arquivo.Integridade. Garante que o arquivo baixado é exatamente o mesmo que está no portal.processadoBOOLEANFlag de controle (0 ou 1).Gestão de Custos: Impede que o robô envie o mesmo arquivo duas vezes para a IA, economizando tokens da API.Tabela: oportunidadesArmazena a inteligência extraída pela IA. Contém tanto dados do passado (resultados) quanto do futuro (avisos de licitação).ColunaTipo SQLDescrição TécnicaImportância para o NegócioidINTEGERChave Primária (Auto Increment).Identificador único da oportunidade.diario_idINTEGERChave Estrangeira (diarios.id).Rastreabilidade. Conecta a inteligência extraída ao documento original.id_processoVARCHAR(100)Código do processo (ex: "Pregão 90/2025").Localizador: É o código que o vendedor digita no portal da transparência para baixar o edital completo.categoriaVARCHAR(100)Tag de classificação (ex: "Limpeza", "TI").Filtro de Interesse: Permite ao usuário ver apenas nichos relevantes para sua empresa.objetoTEXTDescrição completa do item/serviço.O vendedor lê este campo para qualificar o lead ("Eu vendo isso?").valorFLOATValor monetário total (estimado ou contratado).Qualificação Financeira: Define o porte da oportunidade. Se 0, geralmente é sigiloso ou registro de preço.statusVARCHAR(50)Estado atual: "Aberto" ou "Contratado".O Filtro Principal:• Aberto: Ação imediata (Vender).• Contratado: Inteligência competitiva.data_sessaoVARCHAR(100)Data e hora da disputa (ex: "15/02/2026 09h").Lead Time: O dado mais crítico para licitações futuras. Define o prazo final para envio de proposta.vencedorVARCHAR(200)Nome da empresa (se houver).Monitoramento: Mostra quem são os players dominantes na região. Se status for "Aberto", este campo é nulo ou "Em Aberto".cnpj_vencedorVARCHAR(30)CNPJ da empresa vencedora.Permite enriquecimento de dados (buscar sócios, processos e saúde financeira do concorrente).prazoVARCHAR(100)Vigência do contrato (ex: "12 meses").Ciclo de Venda: Cria gatilhos para contatar o órgão público perto do vencimento do contrato atual.localizacaoVARCHAR(255)Endereço de entrega ou execução.Logística. Define custos de frete ou viabilidade técnica de obras.insight_vendaTEXTTexto gerado pela IA.Diferencial Competitivo: Traduz o "juridiquês" em uma dica acionável e estratégica para o vendedor.3. Regras de Negócio e Lógica de DadosStatus e FluxoLead Quente (Venda):status = "Aberto"data_sessao = Data Futuravencedor = "Em Aberto" / NULLInteligência (Monitoramento):status = "Contratado" / "Ratificado" / "Homologado"data_sessao = NULL (Geralmente)vencedor = Nome da ConcorrenteConstrução de LinksO link para o documento original não é salvo no banco para economizar espaço e permitir mudanças de domínio. Ele é construído dinamicamente pela API usando o codigo_origem:Fórmula: https://lencois.mentor.metaway.com.br/recurso/diario/editar/{diarios.codigo_origem}4. Comandos de Manutenção (SQL)Caso precise resetar o banco de dados manualmente durante o desenvolvimento:SQL-- Desativa verificação de chaves para permitir drop em qualquer ordem
SET FOREIGN_KEY_CHECKS = 0;

-- Apaga as tabelas
DROP TABLE IF EXISTS oportunidades;
DROP TABLE IF EXISTS diarios;

-- Reativa verificação
SET FOREIGN_KEY_CHECKS = 1;
