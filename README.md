# ShinySC
A straight-forward wrapper to build customized table links to Statistics Canada data tables.

Customized table links allow for programmatic table customizations and downloading without having to mess around with vectors or data coordinates. With ShinySC you can easily download data for a specific province, time period, table subject by passing in a productId (StatCan table number) and your query terms.

For exaple, if you want to download the table "Building permits, by type of structure and type of work", but just for Alberta, all you need to do is call:

    ShinySC.make_url(34100292,filters={'Geography:['Alberta']})

Which will return a custom URL that can be used to download a CSV file:

    "https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action?pid=3410029201&latestN=&startDate=&endDate=&csvLocale=en&selectedMembers=%5B%5B10%5D%2C%5B1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15%2C16%2C17%2C18%2C19%2C20%2C21%2C22%2C23%2C24%2C25%2C26%2C27%2C28%2C29%2C30%2C31%2C32%2C33%2C34%2C35%2C36%2C37%2C38%2C39%2C40%2C41%2C42%2C43%2C44%2C45%2C46%2C47%2C48%2C49%2C50%2C51%2C52%2C53%2C54%2C55%2C56%2C57%2C58%2C59%2C60%2C61%2C62%2C63%2C64%2C65%2C66%2C67%2C68%2C69%2C70%2C71%2C72%2C73%2C74%2C75%2C76%2C77%2C78%2C79%2C80%2C81%2C82%2C83%2C84%2C85%2C86%2C87%2C88%2C89%5D%2C%5B1%2C3%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15%2C16%2C17%2C18%2C19%2C20%2C21%2C22%2C23%2C24%5D%2C%5B1%2C2%2C3%2C4%2C5%5D%2C%5B1%2C2%2C3%2C4%5D%5D&checkedLevels="
